import json
import logging
import lark_oapi as lark
from lark_oapi.ws import Client
from lark_oapi.api.im.v1.model import P2ImMessageReceiveV1, ReplyMessageRequest, ReplyMessageRequestBody

# 导入业务模块
from project_manager import ProjectManager
from minutes_summarizer import MinutesSummarizer
from doc_manager import DocManager
import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 读取配置
with open("config.json", "r") as f:
    config = json.load(f)

APP_ID = config["APP_ID"]
APP_SECRET = config["APP_SECRET"]

# 初始化 Lark 客户端
client = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).log_level(lark.LogLevel.INFO).build()

# 初始化业务模块
pm = ProjectManager(client, config)
mm = MinutesSummarizer(
    APP_ID, APP_SECRET, 
    config["LLM_API_KEY"], config.get("LLM_BASE_URL"), config.get("LLM_MODEL")
)
dm = DocManager(APP_ID, APP_SECRET)

processed_msg_ids = set()

def reply(msg_id, text):
    resp = client.im.v1.message.reply(ReplyMessageRequest.builder() 
        .message_id(msg_id)
        .request_body(ReplyMessageRequestBody.builder().content(json.dumps({"text": text})).msg_type("text").build())
        .build())
    if resp.success():
        return resp.data.message_id
    else:
        logging.error(f"Failed to reply message: {resp.code} - {resp.msg}")
        return None

from lark_oapi.api.im.v1.model import UpdateMessageRequest, UpdateMessageRequestBody

def update_message(message_id, text):
    request_body = UpdateMessageRequestBody.builder() \
        .msg_type("text") \
        .content(json.dumps({"text": text})) \
        .build()
        
    request = UpdateMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(request_body) \
        .build()
    
    resp = client.im.v1.message.update(request)
    if not resp.success():
        logging.error(f"Failed to update message {message_id}: {resp.code} - {resp.msg}")
        return False
    return True

def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    event = data.event
    msg = event.message
    msg_id = msg.message_id
    
    # 1. 去重
    if msg_id in processed_msg_ids: return
    processed_msg_ids.add(msg_id)
    if len(processed_msg_ids) > 1000: processed_msg_ids.clear()

    # 2. 获取发送者
    sender_id = event.sender.sender_id.open_id
    
    # 3. 解析内容
    try:
        content = json.loads(msg.content)
        text = content.get("text", "").strip()
        mentions = getattr(msg, "mentions", []) or []
    except: return

    # 4. 群聊防打扰
    if msg.chat_type == "group":
        is_at_me = False
        # 获取 Bot ID (Lazy load)
        bot_id = pm.get_bot_id()
        for m in mentions:
            if (bot_id and m.id.open_id == bot_id) or m.name in ["Dobby", "机器人", "Feishu Bot"]:
                is_at_me = True
                break
        if not is_at_me: return

    # 5. 清洗文本 (去除 @Dobby)
    clean_text = text
    for m in mentions:
        clean_text = clean_text.replace(m.key, "").strip()

    # --- 路由分发 (Router) ---

    # A. Help 指令
    if not clean_text or clean_text.lower() in ["help", "帮助", "/start", "怎么用"]:
        reply(msg_id, "👋 我是 Dobby。\n\n1. **项目管理**: 帮我建任务、查任务、完成任务。\n2. **会议纪要**: 发送妙记链接，我自动总结。")
        return

    # B. 会议纪要 (特征: 包含 minutes 链接)
    minutes_token = mm.extract_minutes_token(text) # 用原始文本匹配链接
    if minutes_token:
        # 发送初始处理消息，并获取 message_id
        initial_reply_id = reply(msg_id, "🎧 收到会议录音，正在处理中...")
        
        final_response_text = ""
        doc_url = ""

        try:
            subtitle = mm.fetch_subtitle(minutes_token)
            if not subtitle:
                final_response_text = "❌ 无法读取妙记。请确认已授予机器人权限并分享链接。"
            else:
                summary_result = mm.summarize(subtitle)
                
                if isinstance(summary_result, dict):
                    summary_content = summary_result.get("content", "")
                    summary_title = summary_result.get("title", "会议纪要")
                else:
                    summary_content = str(summary_result)
                    summary_title = "会议纪要"

                # 默认回复文本，如果文档创建失败，则回复总结内容
                final_response_text = summary_content 

                # 尝试存入文档
                try:
                    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                    doc_title = f"{summary_title} - {today_str}"
                    
                    doc_id = dm.create_document(doc_title)
                    if doc_id:
                        dm.add_content(doc_id, summary_content)
                        doc_url = f"https://feishu.cn/docx/{doc_id}"
                        
                        # 文档创建成功，只回复文档链接和状态
                        final_response_text = f"✅ 会议纪要已生成云文档: [{doc_title}]({doc_url})"
                        
                        # 尝试转移所有权
                        if dm.transfer_ownership(doc_id, sender_id):
                            final_response_text += "\n✅ 所有权已转移给你。"
                        else:
                            final_response_text += "\n⚠️ 所有权转移失败，请检查机器人是否具备足够权限（如：云文档所有者转移）。"
                    else:
                        # 文档创建失败，在原总结内容基础上追加错误信息
                        final_response_text += "\n\n❌ 文档创建失败，请检查权限。"
                except Exception as e:
                    # 文档保存异常，在原总结内容基础上追加错误信息
                    final_response_text += f"\n\n❌ 保存文档异常: {e}"


        except Exception as e:
            final_response_text = f"❌ 处理妙记时发生异常: {e}"
        
        # 更新初始消息
        if initial_reply_id:
            update_message(initial_reply_id, final_response_text)
        else: # 如果初始消息发送失败，则直接回复
            reply(msg_id, final_response_text)
        
        return

    # C. 项目管理 (默认兜底)
    # 调用 ProjectManager 进行意图识别和处理
    result = pm.process(clean_text, mentions, sender_id, "User")
    if result:
        reply(msg_id, result)

if __name__ == "__main__":
    # 注册事件回调
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
        .build()

    ws_client = Client(APP_ID, APP_SECRET, event_handler=event_handler, log_level=lark.LogLevel.INFO)
    print("🤖 Dobby (All-in-One) 正在启动...")
    ws_client.start()