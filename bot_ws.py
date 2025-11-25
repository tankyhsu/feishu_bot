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

# --- 辅助函数 ---
def get_text_value(field_value):
    """从多维表格字段中提取纯文本"""
    if isinstance(field_value, str):
        return field_value
    if isinstance(field_value, list) and len(field_value) > 0:
        # 多行文本通常是 [{'text': '...', 'type': 'text'}]
        if isinstance(field_value[0], dict) and "text" in field_value[0]:
            return "".join([item.get("text", "") for item in field_value])
    return str(field_value) if field_value else ""

# --- 业务功能函数 ---

def handle_query_tasks(open_id):
    """查询用户的待办任务"""
    # 策略：全量拉取（最近500条），内存过滤
    # 彻底规避 API Filter 语法错误
    
    req = SearchAppTableRecordRequest.builder() \
        .app_token(BITABLE_APP_TOKEN) \
        .table_id(TABLE_ID) \
        .request_body(SearchAppTableRecordRequestBody.builder() \
            .build()) \
        .build()

    resp = client.bitable.v1.app_table_record.search(req)
    if not resp.success():
        logging.error(f"Query Failed: {resp.code} - {resp.msg}")
        return "❌ 查询出错，请检查后台日志"

    items = resp.data.items or []
    my_tasks = []
    
    for item in items:
        fields = item.fields
        status = fields.get("状态", "待办")
        owners = fields.get("负责人", [])
        
        # 1. 必须未完成
        if status == "已完成":
            continue
        
        # 2. 必须是我的
        if any(o.get("id") == open_id for o in owners):
            my_tasks.append(item)
            
    # 3. 内存排序 (按截止日期倒序, 截止日期可能为空)
    my_tasks.sort(key=lambda x: x.fields.get("截止日期", 0) or 0, reverse=True)

    if not my_tasks:
        return "🎉 你目前没有待办任务！"

    msg_lines = ["📋 **你的待办任务:**"]
    for item in my_tasks:
        fields = item.fields
        # 使用辅助函数提取文本
        name = get_text_value(fields.get("任务描述"))
        quadrant = fields.get("四象限", "未分类")
        status = fields.get("状态", "待办")
        due = datetime.fromtimestamp(fields.get("截止日期", 0)/1000).strftime("%Y-%m-%d") if fields.get("截止日期") else "-"
        msg_lines.append(f"- [{status}] {name} ({quadrant}) 📅{due}")
        
    return "\n".join(msg_lines)


def handle_mark_done(open_id, keyword):
    """将任务标记为已完成"""
    # 策略：全量拉取 + 内存匹配
    # 彻底规避 Filter 报错
    
    req = SearchAppTableRecordRequest.builder() \
        .app_token(BITABLE_APP_TOKEN) \
        .table_id(TABLE_ID) \
        .request_body(SearchAppTableRecordRequestBody.builder().build()) \
        .build()

    resp = client.bitable.v1.app_table_record.search(req)
    if not resp.success(): 
        logging.error(f"Search Failed: {resp.code} - {resp.msg}")
        return f"❌ 查找失败: {resp.msg}"

    items = resp.data.items or []
    target_items = []
    
    # 内存过滤
    for item in items:
        fields = item.fields
        # 使用辅助函数提取文本
        task_name = get_text_value(fields.get("任务描述"))
        status = fields.get("状态", "")
        owners = fields.get("负责人", [])
        
        # 1. 关键词匹配 (简单包含)
        if keyword not in task_name:
            continue
            
        # 2. 必须是未完成的
        if status == "已完成":
            continue
            
        # 3. 必须是我的任务
        if any(o.get("id") == open_id for o in owners):
            target_items.append(item)
            
    if not target_items: return f"🔍 未找到包含 '{keyword}' 的待办任务。"
    
    if len(target_items) > 1:
        names = [get_text_value(i.fields.get("任务描述")) for i in target_items]
        return f"🤔 找到多个匹配任务:\n" + "\n".join([f"- {n}" for n in names])

    record_id = target_items[0].record_id
    task_name = get_text_value(target_items[0].fields.get("任务描述"))
    
    update_req = UpdateAppTableRecordRequest.builder() \
        .app_token(BITABLE_APP_TOKEN) \
        .table_id(TABLE_ID) \
        .record_id(record_id) \
        .request_body(AppTableRecord.builder().fields({"状态": "已完成"}).build()) \
        .build()
        
    if client.bitable.v1.app_table_record.update(update_req).success():
        return f"✅ 已完成: **{task_name}**"
    return "❌ 更新失败"


# --- 获取 Tenant Access Token (用于 requests 调用) ---
def get_tenant_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    if resp.status_code == 200:
        return resp.json().get("tenant_access_token")
    return None

def create_native_task(task_name, due_date_ts, owner_ids):
    """创建飞书原生任务 (Task V2) - 使用 requests 原生调用"""
    token = get_tenant_token()
    if not token:
        return "(鉴权失败)"
        
    url = "https://open.feishu.cn/open-apis/task/v2/tasks"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # 构造负责人
    members = [{"id": oid, "type": "user"} for oid in owner_ids]
    
    payload = {
        "summary": task_name,
        "members": members
    }
    
    if due_date_ts:
        payload["due"] = {"time": str(due_date_ts)}
        
    try:
        resp = requests.post(url, headers=headers, json=payload)
        data = resp.json()
        
        if resp.status_code == 200 and data.get("code") == 0:
            return f"[原生任务ID: {data['data']['task']['guid']}]"
        else:
            logging.error(f"Native Task Create Failed: {resp.text}")
            return "(原生任务创建失败)"
    except Exception as e:
        logging.error(f"Native Task Exception: {e}")
        return "(原生任务异常)"


def handle_create_task(task_name, quadrant, due_date_ts, owner_ids, create_native_task_flag=False):
    """标准化的创建接口 (支持四象限 + 原生任务可选双写)"""
    
    # 1. 写入多维表格 (Bitable)
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
    
    bitable_msg = ""
    if resp.success():
        bitable_msg = "✅ 多维表格已记录"
    else:
        bitable_msg = f"❌ 表格写入失败: {resp.msg}"
        
    # 2. 根据 flag 创建原生任务 (Native Task)
    native_msg = ""
    if create_native_task_flag:
        native_msg = f"\n📱 原生任务已同步 {create_native_task(task_name, due_date_ts, owner_ids)}"
    else:
        native_msg = "\n(原生任务未创建)"
    
    # 3. 返回综合结果
    return f"{bitable_msg}{native_msg}\n📌 {task_name}\n🎯 {quadrant}"


# --- 智能调度核心 ---

def dispatch_command(text, mentions, sender_id, sender_name):
    global BOT_OPEN_ID
    
    # 0. 补救措施：如果全局 ID 还没获取到，尝试从当前消息的 mentions 里找
    if not BOT_OPEN_ID:
        for m in mentions:
            # 适配 Dobby
            if m.name in ["Dobby", "机器人", "Feishu Bot"]:
                BOT_OPEN_ID = m.id.open_id
                logging.info(f"🤖 (Fallback) 从 Mentions 识别到机器人 ID: {BOT_OPEN_ID}")
                break

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
            quadrant = params.get("quadrant", "重要不紧急")
            create_native_task_flag = params.get("create_native_task", False) # 默认不创建原生任务
            
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
                # 策略 A: 名字过滤 (Dobby)
                if m.name in ["Dobby", "机器人", "Feishu Bot"]:
                    continue
                mention_map[m.name] = m.id.open_id
                mention_map[m.key] = m.id.open_id 
            
            for owner_name in llm_owners:
                # 策略 B: 名字过滤 (LLM 提取出来的名字)
                if owner_name in ["Dobby", "机器人", "自己", "Bot"]:
                    continue

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
            
            # 策略 C: ID 过滤 (最终保险)
            if BOT_OPEN_ID and BOT_OPEN_ID in final_owner_ids:
                final_owner_ids.remove(BOT_OPEN_ID)
                
            if not final_owner_ids:
                final_owner_ids = [sender_id]
                
            return handle_create_task(task_name, quadrant, due_date_ts, final_owner_ids, create_native_task_flag)
            
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
        # 过滤机器人 (Dobby)
        if m.name in ["Dobby", "机器人", "Feishu Bot"]:
            clean_text = clean_text.replace(m.key, "").strip()
            continue
            
        if m.key in text:
            owner_ids.append(m.id.open_id)
            clean_text = clean_text.replace(m.key, "").strip()
    
    # 最终排除机器人自己 (正则路径)
    if BOT_OPEN_ID and BOT_OPEN_ID in owner_ids:
        owner_ids.remove(BOT_OPEN_ID)

    if not owner_ids: owner_ids = [sender_id]
    
    tokens = clean_text.split()
    quadrant = "重要不紧急" 
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
        
    return handle_create_task(" ".join(remains) or "未命名", quadrant, due_date_ts, owner_ids, False) # 默认不创建原生任务


# --- 获取机器人自己的 Open ID ---
BOT_OPEN_ID = None
def get_bot_open_id():
    global BOT_OPEN_ID
    try:
        resp = client.bot.v3.info.get()
        if resp.success():
            BOT_OPEN_ID = resp.data.bot.open_id
            logging.info(f"🤖 机器人自己的 Open ID: {BOT_OPEN_ID}")
            return BOT_OPEN_ID
        else:
            logging.error(f"❌ 无法获取机器人自己的 Open ID: {resp.code} - {resp.msg}")
            return None
    except Exception as e:
        logging.error(f"❌ 获取机器人 Open ID 异常: {e}")
        return None

# --- 全局去重缓存 ---
processed_message_ids = set()

# --- 事件入口 ---
def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    global BOT_OPEN_ID
    # 确保 BOT_OPEN_ID 已初始化
    if BOT_OPEN_ID is None:
        get_bot_open_id()

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
    sender_name = "User" 
    
    # 在第一次收到消息时尝试获取机器人自己的 OpenID
    if not BOT_OPEN_ID:
        for m in message.mentions:
            # 适配 Dobby
            if m.id.open_id and m.name in ["Dobby", "机器人", "Feishu Bot"]:
                BOT_OPEN_ID = m.id.open_id
                logging.info(f"🤖 机器人自己的 Open ID 已识别: {BOT_OPEN_ID}")
                break

    # --- 防打扰逻辑 ---
    # 如果是群聊 (group)，且没有 @机器人，则忽略
    # chat_type: "p2p" (私聊) or "group" (群聊)
    if message.chat_type == "group":
        is_mentioned = False
        if hasattr(message, "mentions"):
            for m in message.mentions:
                # 检查是否 @了机器人 (对比 ID 或 名字)
                if (BOT_OPEN_ID and m.id.open_id == BOT_OPEN_ID) or m.name in ["Dobby", "机器人", "Feishu Bot"]:
                    is_mentioned = True
                    break
        
        if not is_mentioned:
            logging.debug(f"🔇 群聊消息但未 @机器人，忽略: {msg_id}")
            return

    try:
        content = json.loads(message.content)
        text = content.get("text", "").strip()
        # 修复: 确保 mentions 永远是列表，防止 SDK 返回 None
        mentions = getattr(message, "mentions", []) or []
    except: return

    # --- 清洗文本 (移除 @mention) ---
    clean_text_for_help = text
    for m in mentions:
        clean_text_for_help = clean_text_for_help.replace(m.key, "").strip()

    # --- 空消息/帮助指令处理 ---
    # 1. 纯空消息 -> 回复帮助
    # 2. 只有帮助指令 -> 回复帮助
    if not clean_text_for_help or clean_text_for_help.lower() in ["help", "帮助", "/start", "怎么用", "使用说明", "功能"]:
        help_msg = """👋 Hi, 我是 Dobby 项目助手！
你可以这样对我说话：

1. **创建任务** (支持自然语言)
   - "明天要把PPT写完，很重要"
   - "提醒我下周一开会" (会创建飞书原生任务)
   
2. **查询任务**
   - "我的任务"
   - "还有啥没做？"

3. **更新状态**
   - "PPT写完啦"
   - "首页Bug修好了"
   
如果不指定负责人，我会把任务分配给你。
"""
        client.im.v1.message.reply(ReplyMessageRequest.builder() \
            .message_id(message.message_id) \
            .request_body(ReplyMessageRequestBody.builder().content(json.dumps({"text": help_msg})).msg_type("text").build()) \
            .build())
        return

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
