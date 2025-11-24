import re
import json
from datetime import datetime

def parse_task_command(event_data):
    """
    解析飞书机器人接收到的群消息，提取任务信息。
    
    Args:
        event_data (dict): 飞书 Webhook 传递的原始 JSON 数据
        
    Returns:
        dict: 包含 task_name, owners, priority, due_date 的字典
    """
    
    # 1. 安全获取消息内容
    try:
        message = event_data.get("event", {}).get("message", {})
        content_json = message.get("content", "{}")
        content = json.loads(content_json)
        text = content.get("text", "").strip()
        mentions = message.get("mentions", [])
    except Exception as e:
        return {"error": f"数据格式错误: {str(e)}"}

    # 2. 初始化结果
    parsed_data = {
        "task_name": "",
        "owners": [],  # 存储 open_id
        "priority": "低", # 默认优先级
        "due_date": None,
        "original_text": text
    }

    # 3. 提取被 @ 的人 (排除 @机器人 自身)
    # 通常机器人的 open_id 在 event.header.app_id 或者需要硬编码排除，
    # 这里我们简单策略：只要是 mention 里的，如果不是机器人名字（通常在 text 里会被移除），就算 owner
    # 更严谨的做法是比对 robot_id，但在集成平台里我们通常把所有非机器人的 @ 都当作执行人
    
    # 在文本中移除 @部分 的 key，飞书 text 通常是 "@_user_1  修复bug"
    # mentions 结构: [{'key': '@_user_1', 'id': {'open_id': 'ou_xxx', ...}, 'name': '张三'}]
    
    clean_text = text
    
    for mention in mentions:
        key = mention["key"]
        # 简单的逻辑：如果文本里包含这个key，我们就记录下来
        if key in text:
            # 这里假设所有 @ 的人都是负责人（除了机器人自己，实际场景需根据 bot_id 过滤）
            # 在集成平台中，可以将 bot_id 作为参数传入进行过滤
            parsed_data["owners"].append(mention["id"]["open_id"])
            
            # 从文本中移除 @占位符
            clean_text = clean_text.replace(key, "").strip()

    # 4. 提取优先级 (高/中/低)
    priority_map = {"高": "High", "中": "Medium", "低": "Low"}
    found_priority = None
    
    # 简单的关键词匹配，从后往前找，避免任务名里包含字
    # 这种简单匹配要求用户指令比较规范，例如放在最后
    tokens = clean_text.split()
    remaining_tokens = []
    
    for token in tokens:
        if token in priority_map:
            parsed_data["priority"] = priority_map[token]
        elif re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", token):
            # 5. 提取日期 (YYYY-MM-DD)
            # 简单校验日期合法性
            try:
                datetime.strptime(token, "%Y-%m-%d")
                parsed_data["due_date"] = token # 飞书多维表格通常接受毫秒时间戳或标准字符串
            except ValueError:
                remaining_tokens.append(token)
        else:
            remaining_tokens.append(token)
            
    # 6. 剩余部分作为任务名
    parsed_data["task_name"] = " ".join(remaining_tokens)
    
    return parsed_data

# --- 本地测试部分 (实际在集成平台中不需要) ---
if __name__ == "__main__":
    # 模拟一个飞书事件 JSON
    mock_event = {
        "event": {
            "message": {
                "content": "{\"text\":\"@_user_1  修复登录Bug 高 2025-12-31\"}",
                "mentions": [
                    {
                        "key": "@_user_1",
                        "id": {"open_id": "ou_123456"},
                        "name": "张三"
                    }
                ]
            }
        }
    }
    
    print("原始输入:", mock_event["event"]["message"]["content"])
    result = parse_task_command(mock_event)
    print("解析结果:", json.dumps(result, indent=2, ensure_ascii=False))
