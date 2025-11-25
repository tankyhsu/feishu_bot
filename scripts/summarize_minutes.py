import json
import re
import requests
from urllib.parse import urlparse
import lark_oapi as lark
from lark_oapi.api.minutes.v1.model import *
from openai import OpenAI

# Load Config
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

# Init Client
client = lark.Client.builder() \
    .app_id(APP_ID) \
    .app_secret(APP_SECRET) \
    .log_level(lark.LogLevel.INFO) \
    .build()

llm_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

def extract_token(url):
    """
    从链接提取 token
    https://meetings.feishu.cn/minutes/obcnxyz123... -> obcnxyz123
    """
    # 简单正则匹配
    match = re.search(r"/minutes/([a-zA-Z0-9]+)", url)
    if match:
        return match.group(1)
    return None

def get_minutes_text(minute_token):
    print(f"📥 正在下载妙记字幕 (Token: {minute_token})...")
    
    # 使用 requests 直接调用 (SDK 有时参数较多，直接调 REST API 更直观)
    # 1. 获取 Tenant Token
    token_resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET}
    )
    tenant_token = token_resp.json().get("tenant_access_token")
    
    # 2. 获取字幕
    # API: GET /open-apis/minutes/v1/minutes/{minute_token}/subtitle
    url = f"https://open.feishu.cn/open-apis/minutes/v1/minutes/{minute_token}/subtitle"
    headers = {"Authorization": f"Bearer {tenant_token}"}
    params = {"size": 5000} # 获取尽量多
    
    resp = requests.get(url, headers=headers, params=params)
    
    if resp.status_code != 200:
        print(f"❌ 获取字幕失败: {resp.text}")
        if resp.status_code == 403:
            print("👉 请确保：1. 机器人开通了'查看妙记'权限并发布。 2. 您已将该妙记'分享'给机器人(设置为可阅读)。")
        return None
        
    data = resp.json().get("data", {})
    sentences = data.get("list", [])
    
    full_text = []
    for s in sentences:
        content = s.get("content", "")
        full_text.append(content)
        
    return "\n".join(full_text)

def summarize_with_ai(text):
    print("🧠 正在进行 AI 总结 (DeepSeek)...")
    
    prompt = f"""
你是一个专业的会议纪要整理助手。请根据以下会议录音转文字内容，整理出一份结构清晰的纪要。

内容如下：
{text[:8000]} 
(注：如果内容过长已截断)

请输出 Markdown 格式，包含以下部分：
1. **📌 核心结论**: 一句话概括会议达成的共识。
2. **📝 关键信息**: 3-5点重要的讨论细节。
3. **✅ 待办事项**: 具体的 Action Items (如有负责人请标注)。
4. **🏷️ 智能标签**: 给出3个分类标签（如 #产品评审 #Bug修复）。

风格要求：简洁、商务、专业。
"""

    try:
        response = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ AI 总结失败: {e}"

if __name__ == "__main__":
    print("🔗 请输入飞书妙记链接 (例如 https://meetings.feishu.cn/minutes/obcn...):")
    url = input("> ").strip()
    
    token = extract_token(url)
    if not token:
        print("❌ 无法识别链接中的 token")
        exit(1)
        
    text = get_minutes_text(token)
    if text:
        print(f"✅ 获取成功 (字数: {len(text)})")
        summary = summarize_with_ai(text)
        print("\n" + "="*30)
        print("📄 会议纪要生成结果")
        print("="*30 + "\n")
        print(summary)
