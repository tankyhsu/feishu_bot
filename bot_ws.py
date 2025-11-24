import json
import logging
import re
import traceback
from datetime import datetime

import lark_oapi as lark
from lark_oapi.ws import Client
from lark_oapi.api.im.v1.model import (
    P2ImMessageReceiveV1, 
    ReplyMessageRequest, 
    ReplyMessageRequestBody
)
from lark_oapi.api.bitable.v1.model import (
    CreateAppTableRecordRequest, 
    AppTableRecord,
    SearchAppTableRecordRequest,
    SearchAppTableRecordRequestBody,
    UpdateAppTableRecordRequest
)

from llm_service import LLMParser

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 读取配置
with open("config.json", "r") as f:
    config = json.load(f)

APP_ID = config["APP_ID"]
APP_SECRET = config["APP_SECRET"]
BITABLE_APP_TOKEN = config["BITABLE_APP_TOKEN"]
TABLE_ID = config["TABLE_ID"]

# 初始化 Feishu Client
client = lark.Client.builder() \
    .app_id(APP_ID) \
    .app_secret(APP_SECRET) \
    .log_level(lark.LogLevel.INFO) \
    .build()

# 初始化 LLM Parser
llm_parser = LLMParser(
    api_key=config.get("LLM_API_KEY", ""),
    base_url=config.get("LLM_BASE_URL", ""),
    model=config.get("LLM_MODEL", "")
)

# --- 业务功能函数 (保持不变) ---

def handle_query_tasks(open_id):
    """查询用户的待办任务"""
    filter_str = f'CurrentValue.[负责人].contains("{open_id}") AND CurrentValue.[状态] != "已完成"'
    
    req = SearchAppTableRecordRequest.builder() \
        .app_token(BITABLE_APP_TOKEN) \
        .table_id(TABLE_ID) \
        .request_body(SearchAppTableRecordRequestBody.builder() \
            .filter(filter_str) \
            .sort(["截止日期 DESC"]) 
            .build()) \
        .build()

    resp = client.bitable.v1.app_table_record.search(req)
    if not resp.success():
        return "❌ 查询出错，请检查后台日志"

    items = resp.data.items or []
    if not items:
        return "🎉 你目前没有待办任务！"

    msg_lines = ["📋 **你的待办任务:**"]
    for item in items:
        fields = item.fields
        name = fields.get("任务描述", "无标题")
        quadrant = fields.get("四象限", "未分类")
        status = fields.get("状态", "待办")
        due = datetime.fromtimestamp(fields.get("截止日期", 0)/1000).strftime("%Y-%m-%d") if fields.get("截止日期") else "-"
        msg_lines.append(f"- [{status}] {name} ({quadrant}) 📅{due}")
        
    return "\n".join(msg_lines)


def handle_mark_done(open_id, keyword):
    """将任务标记为已完成"""
    filter_str = f'CurrentValue.[负责人].contains("{open_id}") AND CurrentValue.[任务描述].contains("{keyword}") AND CurrentValue.[状态] != "已完成"'
    
    req = SearchAppTableRecordRequest.builder() \
        .app_token(BITABLE_APP_TOKEN) \
        .table_id(TABLE_ID) \
        .request_body(SearchAppTableRecordRequestBody.builder() \
            .filter(filter_str) \
            .build()) \
        .build()

    resp = client.bitable.v1.app_table_record.search(req)
    if not resp.success(): return f"❌ 查找失败: {resp.msg}"

    items = resp.data.items or []
    if not items: return f"🔍 未找到包含 '{keyword}' 的待办任务。"
    
    if len(items) > 1:
        names = [i.fields.get("任务描述", "") for i in items]
        return f"🤔 找到多个匹配任务:\n" + "\n".join([f"- {n}" for n in names])

    record_id = items[0].record_id
    task_name = items[0].fields.get("任务描述", "")
    
    update_req = UpdateAppTableRecordRequest.builder() \
        .app_token(BITABLE_APP_TOKEN) \
        .table_id(TABLE_ID) \
        .record_id(record_id) \
        .request_body(AppTableRecord.builder().fields({"状态": "已完成"}).build()) \
        .build()
        
    if client.bitable.v1.app_table_record.update(update_req).success():
        return f"✅ 已完成: **{task_name}**"
    return "❌ 更新失败"


def handle_create_task(task_name, quadrant, due_date_ts, owner_ids):
    """标准化的创建接口 (支持四象限)"""
    fields = {
        "任务描述": task_name,
        "四象限": quadrant, # 新字段
        "状态": "待办",
        "负责人": [{"id": oid} for oid in owner_ids]
    }
    
    if due_date_ts:
        fields["截止日期"] = due_date_ts

    req = CreateAppTableRecordRequest.builder() \
        .app_token(BITABLE_APP_TOKEN) \
        .table_id(TABLE_ID) \
        .request_body(AppTableRecord.builder().fields(fields).build()) \
        .build()

    resp = client.bitable.v1.app_table_record.create(req)
    if resp.success():
        return f"✅ 任务已创建\n📌 {task_name}\n🎯 {quadrant}"
    return f"❌ 创建失败: {resp.msg}"


# --- 智能调度核心 ---

def dispatch_command(text, mentions, sender_id, sender_name):
    # 1. 尝试使用 LLM 解析
    llm_result = llm_parser.parse(text, context_user=sender_name)
    
    # 2. 如果 LLM 成功，使用 LLM 结果
    if llm_result:
        action = llm_result.get("action")
        params = llm_result.get("params", {})
        
        if action == "query":
            return handle_query_tasks(sender_id)
            
        elif action == "update_status":
            keyword = params.get("keyword")
            if keyword:
                return handle_mark_done(sender_id, keyword)
            return "❓ 请提供要更新的任务关键词"
            
        elif action == "create":
            # 提取参数
            task_name = params.get("task_name", "未命名任务")
            # 新逻辑: 提取象限
            quadrant = params.get("quadrant", "重要不紧急")
            
            due_date_str = params.get("due_date")
            due_date_ts = None
            if due_date_str:
                try:
                    dt = datetime.strptime(due_date_str, "%Y-%m-%d")
                    due_date_ts = int(dt.timestamp() * 1000)
                except: pass
            
            # 负责人处理
            llm_owners = params.get("owners", [])
            final_owner_ids = []
            
            mention_map = {}
            for m in mentions:
                mention_map[m.name] = m.id.open_id
                mention_map[m.key] = m.id.open_id 
            
            for owner_name in llm_owners:
                matched = False
                if owner_name in mention_map:
                    final_owner_ids.append(mention_map[owner_name])
                    matched = True
                else:
                    for m_name, m_id in mention_map.items():
                        if owner_name in m_name or m_name in owner_name:
                            final_owner_ids.append(m_id)
                            matched = True
                            break
            
            final_owner_ids = list(set(final_owner_ids))
            if not final_owner_ids:
                final_owner_ids = [sender_id]
                
            return handle_create_task(task_name, quadrant, due_date_ts, final_owner_ids)
            
        elif action == "unknown":
            pass 

    # 3. 降级逻辑 (正则映射到四象限)
    logging.info("🔄 Using Fallback Regex Logic")
    
    if any(k in text for k in ["查询", "我的任务", "list"]):
        return handle_query_tasks(sender_id)
    
    if text.startswith("完成 ") or text.startswith("done "):
        keyword = text.split(" ", 1)[1].strip()
        return handle_mark_done(sender_id, keyword)

    clean_text = text
    owner_ids = []
    for m in mentions:
        if m.key in text:
            owner_ids.append(m.id.open_id)
            clean_text = clean_text.replace(m.key, "").strip()
    if not owner_ids: owner_ids = [sender_id]
    
    tokens = clean_text.split()
    quadrant = "重要不紧急" # 默认 P1
    due_date_ts = None
    remains = []
    
    # 简单的关键词映射
    p_map = {
        "高": "重要且紧急", "urgent": "重要且紧急",
        "中": "重要不紧急", "normal": "重要不紧急",
        "低": "不重要不紧急", "low": "不重要不紧急"
    }
    
    for t in tokens:
        if t in p_map: quadrant = p_map[t]
        elif re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", t):
            try: due_date_ts = int(datetime.strptime(t, "%Y-%m-%d").timestamp()*1000)
            except: remains.append(t)
        else: remains.append(t)
        
    return handle_create_task(" ".join(remains) or "未命名", quadrant, due_date_ts, owner_ids)


# --- 全局去重缓存 ---
processed_message_ids = set()

# --- 事件入口 ---
def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    event = data.event
    message = event.message
    msg_id = message.message_id
    
    # 1. 消息去重
    if msg_id in processed_message_ids:
        logging.warning(f"🔁 重复消息，跳过: {msg_id}")
        return
    processed_message_ids.add(msg_id)
    
    # 简单清理缓存 (防止无限增长)
    if len(processed_message_ids) > 1000:
        processed_message_ids.clear()

    sender_id = event.sender.sender_id.open_id
    sender_name = "User" # 消息事件中通常不带发送者名字，需要额外API查，暂忽略或从content推断
    
    try:
        content = json.loads(message.content)
        text = content.get("text", "").strip()
        mentions = message.mentions if hasattr(message, "mentions") else []
    except: return

    logging.info(f"📩 Msg: {text}")
    reply = dispatch_command(text, mentions, sender_id, sender_name)
    
    if reply:
        client.im.v1.message.reply(ReplyMessageRequest.builder() \
            .message_id(message.message_id) \
            .request_body(ReplyMessageRequestBody.builder().content(json.dumps({"text": reply})).msg_type("text").build()) \
            .build())

if __name__ == "__main__":
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
        .build()

    ws_client = Client(APP_ID, APP_SECRET, event_handler=event_handler, log_level=lark.LogLevel.INFO)
    print("🤖 AI 增强版机器人正在启动...")
    print("👉 请确保 config.json 中配置了 LLM_API_KEY，否则将回退到正则模式。")
    ws_client.start()
