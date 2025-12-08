# 飞书机器人项目管理助手 - 架构与实施指南

## 1. 整体设计 (High-Level Design)

### 1.1 目标
在飞书群聊中，通过 `@机器人` 发送特定格式的自然语言指令，自动解析并将任务录入到“飞书多维表格”中，实现任务的自动化创建与分配。

### 1.2 核心架构 (Serverless / No-Code)
本项目完全基于 **飞书集成平台 (AnyCross)** 构建，无外部服务器依赖。

*   **触发源**: 飞书群聊消息事件 (Im Message Receive)。
*   **处理核心**: AnyCross 集成流。
    *   **节点 1 (触发)**: 监听群聊中 @机器人的消息。
    *   **节点 2 (逻辑)**: Python 脚本节点，解析非结构化文本为结构化数据。
    *   **节点 3 (执行)**: 调用多维表格 API 新增记录。
*   **存储层**: 飞书多维表格 (Bitable)。

### 1.3 交互流程
1.  用户在群内发送: `@张三 @机器人 fix: 首页登录报错 高 2025-12-31`
2.  机器人捕获消息。
3.  脚本解析出:
    *   **任务**: "fix: 首页登录报错"
    *   **负责人**: "张三" (OpenID: ou_xxxx)
    *   **优先级**: "High"
    *   **截止日期**: "2025-12-31"
4.  机器人将上述字段写入多维表格对应列。

---

## 2. 详细设计 (Detailed Design)

### 2.1 多维表格数据模型
在配置集成流之前，必须先建立好表格。

| 字段名 | 字段类型 | 选项配置 (如适用) | 说明 |
| :--- | :--- | :--- | :--- |
| **任务名称** | 多行文本 | - | 任务的具体描述 |
| **负责人** | 人员 | - | 支持多选 |
| **优先级** | 单选 | 高, 中, 低 | 对应代码解析出的 High/Medium/Low |
| **截止日期** | 日期 | yyyy-MM-dd | - |
| **创建时间** | 创建时间 | - | 自动生成 |

### 2.2 解析逻辑 (Python)
这是运行在 AnyCross "Python 脚本" 节点中的核心代码。

**输入 (Input)**: 飞书事件 JSON (包含 `text` 和 `mentions`)。
**输出 (Output)**: 结构化字典 (JSON)。

**指令格式规范**:
> `@执行人(可选) @机器人 <任务描述> <优先级(可选)> <日期(可选)>`
> *顺序不强制，但建议日期和优先级放在末尾以便更精准匹配。*

---

## 3. 实施代码 (AnyCross 专用)

请将以下代码完整复制到集成平台的 **Python 脚本** 节点中。

```python
import json
import re
from datetime import datetime

def execute(context, input_data):
    """
    AnyCross Python 节点入口函数
    :param context: 运行上下文
    :param input_data: 上游节点传入的数据 (通常配置为整个 event 消息体)
    :return: dict, 输出给下游节点使用
    """
    
    # --- 1. 数据安全获取 ---
    # 根据实际配置，input_data 可能直接就是 message 或者是 event
    # 这里做兼容处理，假设传入的是 event 结构
    try:
        # 尝试从 event 中获取 message，如果 input_data 本身就是 message 则直接用
        message = input_data.get("event", {}).get("message", input_data)
        content_str = message.get("content", "{}")
        content_dict = json.loads(content_str)
        raw_text = content_dict.get("text", "").strip()
        mentions = message.get("mentions", [])
    except Exception as e:
        return {
            "success": False,
            "error": f"数据解析失败: {str(e)}",
            "debug_input": str(input_data) # 调试用
        }

    # --- 2. 初始化输出结构 ---
    result = {
        "success": True,
        "task_name": "",
        "owner_ids": [],  # 这是给多维表格人员字段用的 (OpenID 列表)
        "priority": "低", # 默认值
        "due_date": None
    }

    # --- 3. 提取负责人 (排除机器人自己) ---
    # 逻辑：遍历 mentions，只要在文本中出现了，就提取 ID
    # 注意：实际使用中，建议在集成平台配置中过滤掉机器人自己的 ID，或者在此处硬编码排除
    clean_text = raw_text
    
    for mention in mentions:
        key = mention["key"] # 例如 "@_user_1"
        open_id = mention["id"]["open_id"]
        
        if key in raw_text:
            # 可以在这里加判断：if open_id != "机器人的ID":
            result["owner_ids"].append(open_id)
            
            # 从文本中移除 @及名字，避免干扰任务名解析
            # 飞书原始文本是 "@_user_1 " (带key)，我们把 key 删掉
            clean_text = clean_text.replace(key, "").strip()

    # --- 4. 提取优先级 & 日期 ---
    # 策略：将文本按空格拆分，从后往前检查是否符合 日期 或 优先级 格式
    # 剩下的部分自动归为 "任务名称"
    
    priority_map = {
        "高": "高", "high": "高", "urgent": "高",
        "中": "中", "medium": "中", "normal": "中",
        "低": "低", "low": "低"
    }
    
    tokens = clean_text.split()
    remaining_tokens = []
    
    for token in tokens:
        # 检查优先级
        if token.lower() in priority_map:
            result["priority"] = priority_map[token.lower()]
        # 检查日期 (YYYY-MM-DD)
        elif re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", token):
            try:
                datetime.strptime(token, "%Y-%m-%d")
                # 飞书表格通常接受 13位毫秒时间戳 或 "YYYY-MM-DD" 字符串
                # 为了稳妥，直接传字符串，飞书一般能自动识别
                result["due_date"] = token 
            except ValueError:
                remaining_tokens.append(token) # 格式像日期但无效
        else:
            remaining_tokens.append(token)
            
    # --- 5. 组装最终任务名 ---
    result["task_name"] = " ".join(remaining_tokens)
    
    # 如果没解析出任务名，给个默认提示
    if not result["task_name"]:
        result["task_name"] = "未命名任务 (请检查指令格式)"

    return result
```

## 4. 系统日志 (System Logging)

项目采用集中式的日志管理机制，以支持长期运行和问题排查。

### 4.1 日志策略
*   **集中化配置**: 所有模块统一使用 `utils.logger.setup_logging(config)` 进行初始化。
*   **文件轮转 (Rotation)**: 使用 `RotatingFileHandler` 防止日志无限增长。
    *   默认大小限制: 10MB
    *   默认保留备份数: 5个
*   **配置项**: 可在 `config.json` 中自定义:
    *   `LOG_FILE`: 日志文件路径 (默认 `logs/bot.log`)
    *   `LOG_MAX_BYTES`: 单个文件大小上限 (Bytes)
    *   `LOG_BACKUP_COUNT`: 保留文件数量
    *   `LOG_LEVEL`: 日志级别 (INFO/DEBUG/ERROR)

### 4.2 Supervisor 集成
在 `supervisord.conf` 中，已配置 `stdout_logfile_maxbytes` 和 `stderr_logfile_maxbytes`，确保 Supervisor 捕获的控制台输出（Console Output）也会自动轮转，避免磁盘占满。
