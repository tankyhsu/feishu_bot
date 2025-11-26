import json
import logging
import re
import requests
import lark_oapi as lark
from lark_oapi.ws import Client
from lark_oapi.api.im.v1.model import P2ImMessageReceiveV1, ReplyMessageRequest, ReplyMessageRequestBody
from openai import OpenAI

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 读取配置 (假设 config.json 在上一级目录，或者需要复制进来)
# 为了方便，我们在运行时假设当前目录是 feishu_minutes_bot，或者显式指定路径
try:
    with open("../config.json", "r") as f:
        config = json.load(f)
except:
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except:
        print("❌ 找不到 config.json")
        exit(1)

APP_ID = config["APP_ID"]
APP_SECRET = config["APP_SECRET"]
LLM_API_KEY = config.get("LLM_API_KEY")
LLM_BASE_URL = config.get("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = config.get("LLM_MODEL", "deepseek-chat")

# 初始化客户端
ws_client = None
client = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).log_level(lark.LogLevel.INFO).build()
llm_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

# --- 工具函数 ---

def get_tenant_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    if resp.status_code == 200:
        return resp.json().get("tenant_access_token")
    return None

def extract_minutes_token(text):
    # 匹配 https://meetings.feishu.cn/minutes/obcnxyz...
    pattern = r"(https?://[a-zA-Z0-9.-]*feishu\.cn/minutes/([a-zA-Z0-9]+))"
    match = re.search(pattern, text)
    if match:
        return match.group(2) # 返回 token
    return None

def fetch_minutes_subtitle(token):
    """获取妙记字幕"""
    access_token = get_tenant_token()
    if not access_token: return None
    
    url = f"https://open.feishu.cn/open-apis/minutes/v1/minutes/{token}/transcript"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            logging.error(f"❌ 获取妙记失败: {resp.text}")
            return None
            
        try:
            data = resp.json()
            if data.get("code") != 0:
                logging.error(f"❌ 获取妙记API错误: {data}")
                return None
            
            resp_data = data.get("data", {})
            if "content" in resp_data: return resp_data["content"]
            if "text" in resp_data: return resp_data["text"]
            
            return f"RAW_JSON: {resp.text}"
        except:
            return resp.text
            
    except Exception as e:
        logging.error(f"❌ 获取妙记异常: {e}")
        return None

def summarize_content(text):
    """调用 LLM 总结"""
    if not text: return "❌ 无法获取会议内容（可能是权限不足或链接无效）"
    
    logging.info(f"🧠 开始总结，原文长度: {len(text)}")
    
    prompt = """
你是一个专业的会议纪要秘书。请根据以下会议录音文本，整理出一份结构化的会议纪要。

### 格式要求 (Markdown):
1. **📌 核心议题**: 一句话概括会议主题。
2. **📝 关键细节**: 列出3-5个讨论重点。
3. **✅ 待办事项 (Action Items)**: 具体的后续行动及负责人。
4. **💡 关键决策**: 会议达成的结论。

### 录音文本:
"""
    # 截断防止 Token 溢出 (根据模型能力调整，DeepSeek 支持长窗口，但为了省钱先截取前 10k 字符)
    content_input = text[:15000] 
    
    try:
        resp = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": content_input}
            ],
            temperature=0.3
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"❌ AI 总结失败: {e}"

# --- 事件处理 ---

def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    event = data.event
    message = event.message
    msg_id = message.message_id
    
    try:
        content = json.loads(message.content)
        text = content.get("text", "").strip()
    except: return

    # 1. 检测是否包含妙记链接
    minutes_token = extract_minutes_token(text)
    if not minutes_token:
        return # 不是妙记链接，忽略

    logging.info(f"🎙️ 检测到妙记链接，Token: {minutes_token}")
    
    # 2. 发送“正在处理”提示 (因为 AI 可能很慢)
    # 飞书 API 支持回复消息
    loading_msg = "🤖 正在听录音并整理纪要，请稍候..."
    client.im.v1.message.reply(ReplyMessageRequest.builder() \
            .message_id(msg_id) \
            .request_body(ReplyMessageRequestBody.builder().content(json.dumps({"text": loading_msg})).msg_type("text").build())
            .build())

    # 3. 获取字幕
    subtitle = fetch_minutes_subtitle(minutes_token)
    if not subtitle:
        fail_msg = "❌ 无法读取妙记内容。请确认：\n1. 机器人已开通'妙记'权限。\n2. 您已将该妙记**分享**给机器人（设置为可阅读）。"
        client.im.v1.message.reply(ReplyMessageRequest.builder().message_id(msg_id).request_body(ReplyMessageRequestBody.builder().content(json.dumps({"text": fail_msg})).msg_type("text").build()).build())
        return

    # 4. AI 总结
    summary = summarize_content(subtitle)
    
    # 5. 回复结果
    client.im.v1.message.reply(ReplyMessageRequest.builder() \
            .message_id(msg_id) \
            .request_body(ReplyMessageRequestBody.builder().content(json.dumps({"text": summary})).msg_type("text").build())
            .build())

if __name__ == "__main__":
    # 注册事件回调
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
        .build()

    ws_client = Client(APP_ID, APP_SECRET, event_handler=event_handler, log_level=lark.LogLevel.INFO)
    print("🎙️ 会议纪要助手 (Minutes Bot) 正在启动...")
    ws_client.start()
