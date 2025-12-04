import json
import logging
import threading
from datetime import datetime
from lark_oapi.api.im.v1.model import P2ImMessageReceiveV1

class MessageHandler:
    def __init__(self, config, im_service, task_service, llm_service, minutes_handler, rss_service):
        self.config = config
        self.im = im_service
        self.task = task_service
        self.llm = llm_service
        self.minutes = minutes_handler
        self.rss = rss_service
        self.processed_msg_ids = set()
        self.lock = threading.Lock()

    def handle(self, data: P2ImMessageReceiveV1):
        event = data.event
        msg = event.message
        msg_id = msg.message_id
        
        # 1. Deduplication (Thread-safe)
        with self.lock:
            if msg_id in self.processed_msg_ids: return
            self.processed_msg_ids.add(msg_id)
            if len(self.processed_msg_ids) > 1000: self.processed_msg_ids.clear()

        # 2. Start a thread to process the message asynchronously
        threading.Thread(target=self._process_message, args=(data,)).start()

    def _process_message(self, data: P2ImMessageReceiveV1):
        event = data.event
        msg = event.message
        msg_id = msg.message_id

        # 3. Get Sender
        sender_id = event.sender.sender_id.open_id
        sender_name = "User" 
        
        # 4. Parse Content
        try:
            content = json.loads(msg.content)
            text = content.get("text", "").strip()
            mentions = getattr(msg, "mentions", []) or []
        except: return

        # 5. Group Chat Filter
        if msg.chat_type == "group":
            logging.info(f"Received group message in chat_id: {msg.chat_id}") 
            is_at_me = False
            bot_id = self.task.get_bot_id()
            for m in mentions:
                if (bot_id and m.id.open_id == bot_id) or m.name in ["Dobby", "机器人", "Feishu Bot"]:
                    is_at_me = True
                    break
            if not is_at_me: return

        # 6. Clean Text (Remove @Dobby)
        clean_text = text
        for m in mentions:
            clean_text = clean_text.replace(m.key, "").strip()

        # --- Router ---

        try:
            # A. Help
            if not clean_text or clean_text.lower() in ["help", "帮助", "/start", "怎么用"]:
                self.im.reply(msg_id, "👋 我是 Dobby。\n\n1. **项目管理**: 帮我建任务、查任务、完成任务。\n2. **会议纪要**: 发送妙记链接，我自动总结。\n3. **RSS早报**: 发送 'RSS' 或 '早报' 获取最新资讯。")
                return

            # B. RSS Digest
            if clean_text.lower() in ["rss", "早报", "新闻", "digest"]:
                self.im.reply(msg_id, "📰 正在抓取并生成 RSS 早报，请稍候...")
                digest = self.rss.fetch_and_summarize()
                self.im.reply(msg_id, digest)
                return

            # C. Minutes (Delegate to MinutesHandler)
            if self.minutes.handle(msg_id, text, sender_id):
                return

            # D. Task Management (Process Intent)
            response = self._process_task_command(clean_text, mentions, sender_id, sender_name)
            if response:
                self.im.reply(msg_id, response)
        except Exception as e:
            logging.error(f"Error processing message {msg_id}: {e}")

    def _process_task_command(self, text, mentions, sender_id, sender_name):
        # 1. LLM Parse
        res = self.llm.parse(text, sender_name)
        
        # 2. Logic Dispatch
        if res:
            action = res.get("action")
            p = res.get("params", {})
            
            if action == "query":
                return self.task.handle_query(sender_id)
            
            if action == "update_status":
                return self.task.handle_mark_done(sender_id, p.get("keyword"))
            
            if action == "create":
                # Resolve Owners
                bot_id = self.task.get_bot_id()
                owners = []
                mention_map = {m.name: m.id.open_id for m in mentions if m.name not in ["Dobby", "机器人", "Feishu Bot"]}
                
                for name in p.get("owners", []):
                    if name in mention_map:
                        owners.append(mention_map[name])
                
                # Fallback owner logic
                if not owners: owners = [sender_id]
                if bot_id and bot_id in owners:
                    owners.remove(bot_id)
                if not owners: owners = [sender_id]
                
                # Resolve Date
                due = None
                if p.get("due_date"):
                    try:
                        due = int(datetime.strptime(p.get("due_date"), "%Y-%m-%d").timestamp()*1000)
                    except: pass
                
                return self.task.handle_create(
                    p.get("task_name"), 
                    p.get("quadrant"), 
                    due, 
                    owners, 
                    p.get("create_native_task", False)
                )
        
        # 3. Fallback Regex/Default Logic
        # If LLM fails or returns unknown, treat as a simple task creation
        return self.task.handle_create(text, "重要不紧急", None, [sender_id], False)