import json
import logging
import re
import traceback
from datetime import datetime

import lark_oapi as lark
from lark_oapi.ws import Client

# 显式导入需要的 Model 类 (修正为全名 Request)
from lark_oapi.api.im.v1.model import (
    P2ImMessageReceiveV1, 
    ReplyMessageRequest, 
    ReplyMessageRequestBody
)
from lark_oapi.api.bitable.v1.model import (
    CreateAppTableRecordRequest, 
    AppTableRecord
)

# 配置日志
logging.basicConfig(level=logging.INFO)

# 读取配置
with open("config.json", "r") as f:
    config = json.load(f)

APP_ID = config["APP_ID"]
APP_SECRET = config["APP_SECRET"]
BITABLE_APP_TOKEN = "DR8mbUoyUazoQ9sk0VTcB5sLnkh"
TABLE_ID = "tbl01oWhlWFaEQsk" 

# 业务逻辑：解析指令
def parse_task_command(text, mentions):
    result = {
        "task_name": "",
        "owner_ids": [],
        "priority": "低",
        "due_date": None
    }
    
    clean_text = text
    
    for mention in mentions:
        key = mention.key
        open_id = mention.id.open_id
        
        if key in text:
            result["owner_ids"].append(open_id)
            clean_text = clean_text.replace(key, "").strip()

    priority_map = {
        "高": "High", "high": "High", "urgent": "High",
        "中": "Medium", "medium": "Medium", "normal": "Medium",
        "低": "Low", "low": "Low"
    }
    
    tokens = clean_text.split()
    remaining_tokens = []
    
    for token in tokens:
        token_lower = token.lower()
        if token in priority_map:
             if priority_map[token] == "High": result["priority"] = "高"
             elif priority_map[token] == "Medium": result["priority"] = "中"
             elif priority_map[token] == "Low": result["priority"] = "低"
        elif token_lower in priority_map:
             if priority_map[token_lower] == "High": result["priority"] = "高"
             elif priority_map[token_lower] == "Medium": result["priority"] = "中"
             elif priority_map[token_lower] == "Low": result["priority"] = "低"

        elif re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", token):
            try:
                datetime.strptime(token, "%Y-%m-%d")
                dt = datetime.strptime(token, "%Y-%m-%d")
                result["due_date"] = int(dt.timestamp() * 1000)
            except ValueError:
                remaining_tokens.append(token)
        else:
            remaining_tokens.append(token)
            
    result["task_name"] = " ".join(remaining_tokens)
    if not result["task_name"]:
        result["task_name"] = "未命名任务"
        
    return result

# 业务逻辑：写入多维表格
def create_bitable_record(client, data):
    fields = {
        "任务描述": data["task_name"],
        "优先级": data["priority"],
    }
    
    if data["due_date"]:
        fields["截止日期"] = data["due_date"]
        
    if data["owner_ids"]:
        fields["负责人"] = [{"id": oid} for oid in data["owner_ids"]]

    # 构造请求
    req = CreateAppTableRecordRequest.builder() \
        .app_token(BITABLE_APP_TOKEN) \
        .table_id(TABLE_ID) \
        .request_body(AppTableRecord.builder().fields(fields).build()) \
        .build()

    resp = client.bitable.v1.app_table_record.create(req)
    
    if not resp.success():
        logging.error(f"写入表格失败: {resp.code} - {resp.msg} - {resp.error}")
        return None
    
    return resp.data.record.record_id

# 事件处理器
def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    event = data.event
    message = event.message
    content = json.loads(message.content)
    text = content.get("text", "")
    mentions = message.mentions if hasattr(message, "mentions") else []
    
    logging.info(f"收到消息: {text}")
    parsed = parse_task_command(text, mentions)
    logging.info(f"解析结果: {parsed}")
    
    try:
        record_id = create_bitable_record(api_client, parsed)
        
        if record_id:
            reply_text = f"✅ 任务已创建\n任务: {parsed['task_name']}\n优先级: {parsed['priority']}"
        else:
            reply_text = "❌ 任务创建失败，请检查后台日志。"
            
        # 使用修正后的类名
        reply_req = ReplyMessageRequest.builder() \
            .message_id(message.message_id) \
            .request_body(ReplyMessageRequestBody.builder() \
                .content(json.dumps({"text": reply_text})) \
                .msg_type("text") \
                .build()) \
            .build()
            
        api_client.im.v1.message.reply(reply_req)
        
    except Exception as e:
        logging.error(f"处理异常: {e}")
        traceback.print_exc()


# 初始化 API 客户端
api_client = lark.Client.builder() \
    .app_id(APP_ID) \
    .app_secret(APP_SECRET) \
    .log_level(lark.LogLevel.INFO) \
    .build()

if __name__ == "__main__":
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
        .build()

    ws_client = Client(APP_ID, APP_SECRET, event_handler=event_handler, log_level=lark.LogLevel.INFO)
    
    print("🤖 机器人正在启动 (WebSocket模式)...")
    ws_client.start()
