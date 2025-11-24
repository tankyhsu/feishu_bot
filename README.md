# 飞书智能项目管理机器人 (AI Enhanced)

基于飞书集成平台与 DeepSeek 大模型的智能任务管理机器人，支持自然语言交互、四象限任务管理、自动分配负责人。

## 🌟 核心功能

### 1. 🧠 AI 语义理解
- **自然语言创建**: "帮我安排明天修一下首页Bug，挺急的" -> 自动识别任务、时间、紧急程度。
- **智能负责人分配**: 
    - 识别 "@张三" 并自动映射到 OpenID。
    - 智能兜底：如果未指定或找不到人，默认分配给指令发送者。
- **意图识别**: 区分创建 (Create)、查询 (Query)、更新 (Update) 意图。

### 2. 📊 四象限任务管理 (Eisenhower Matrix)
废弃传统的高中低优先级，采用更科学的四象限法则：
- 🔴 **重要且紧急**: 立即做 (e.g. 线上故障)
- 🟡 **重要不紧急**: 计划做 (e.g. 架构规划)
- 🔵 **紧急不重要**: 授权做 (e.g. 拿快递)
- ⚪ **不重要不紧急**: 减少做 (e.g. 琐事)

### 3. 🔄 全流程闭环
- **创建**: 支持自然语言和正则兜底。
- **查询**: "我的任务" -> 列出名下待办。
- **更新**: "完成 首页Bug" -> 自动标记为已完成。

---

## 🛠 技术架构

- **语言**: Python 3.9+
- **框架**: `lark-oapi` (飞书 SDK), `openai` (LLM SDK)
- **存储**: 飞书多维表格 (Bitable)
- **部署**: WebSocket 长连接 (无需公网 IP)

### 文件结构
```
.
├── bot_ws.py           # 主程序：WebSocket 服务、事件分发、业务逻辑
├── llm_service.py      # AI 服务：封装 DeepSeek/OpenAI 调用
├── config.json         # 配置文件：AppID, Secret, Token, LLM Key
├── requirements.txt    # 依赖列表
└── scripts/            # 初始化与工具脚本
    ├── init_bitable.py
    └── setup_table_only.py
```

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置 `config.json`
```json
{
  "APP_ID": "cli_xxx",
  "APP_SECRET": "xxx",
  "BITABLE_APP_TOKEN": "xxx",
  "TABLE_ID": "xxx",
  "LLM_API_KEY": "sk-xxx",
  "LLM_BASE_URL": "https://api.deepseek.com",
  "LLM_MODEL": "deepseek-chat"
}
```

### 3. 启动机器人
```bash
python3 bot_ws.py
```

## 📝 更新日志

### v2.0 (2025-11-24)
- **Feature**: 引入 DeepSeek 大模型，实现自然语言理解。
- **Refactor**: 重构多维表格结构，移除“优先级”，新增“四象限”字段。
- **Fix**: 修复了消息重复处理 (Double Posting) 的 Bug。
- **Fix**: 优化了负责人分配逻辑，支持 Mention 精确匹配与兜底。

### v1.0
- 基础版本：支持正则指令解析，对接飞书多维表格。