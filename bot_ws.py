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
    client.im.v1.message.reply(ReplyMessageRequest.builder() 
        .message_id(msg_id)
        .request_body(ReplyMessageRequestBody.builder().content(json.dumps({"text": text})).msg_type("text").build())
        .build())

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
        reply(msg_id, "🎧 收到会议录音，正在收听并整理纪要 (预计1分钟)...")
        
        subtitle = mm.fetch_subtitle(minutes_token)
        if not subtitle:
            reply(msg_id, "❌ 无法读取妙记。请确认已授予机器人权限并分享链接。")
            return
            
        summary = mm.summarize(subtitle)
        reply(msg_id, summary)

        # 存入文档
        try:
            reply(msg_id, "📄 正在生成云文档...")
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            doc_title = f"会议纪要 - {today_str}"
            doc_id = dm.create_document(doc_title)
            if doc_id:
                dm.add_content(doc_id, summary)
                doc_url = f"https://feishu.cn/docx/{doc_id}"
                reply(msg_id, f"✅ 文档已保存: [{doc_title}]({doc_url})")
            else:
                reply(msg_id, "❌ 文档创建失败，请检查权限。")
        except Exception as e:
            reply(msg_id, f"❌ 保存文档异常: {e}")
        
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