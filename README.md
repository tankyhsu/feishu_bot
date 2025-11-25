# 飞书智能项目管理机器人 (Dobby) - v2.3

基于飞书集成平台与 DeepSeek 大模型的智能任务管理机器人，支持自然语言交互、四象限任务管理、自动分配负责人，并具备企业级稳定性。

## 🌟 核心功能

### 1. 🧠 AI 语义理解 (DeepSeek)
- **自然语言创建**: "帮我安排明天修一下首页Bug，挺急的" -> 自动识别任务、时间、紧急程度。
- **智能负责人分配**: 
    - 自动识别 `@提及` 的成员并映射 OpenID。
    - **智能兜底**: 明确排除机器人自己 (Dobby)，若未指定人选，默认分配给指令发送者。
- **意图识别**: 精准区分创建 (Create)、查询 (Query)、更新 (Update) 意图。
- **原生任务联动**: 仅当用户提到 "提醒我"、"建个任务" 时，才会同步创建飞书原生 Task (Task V2)，避免打扰。

### 2. 📊 四象限任务管理 (Eisenhower Matrix)
采用科学的时间管理法则：
- 🔴 **重要且紧急**: 立即做 (e.g. 线上故障)
- 🟡 **重要不紧急**: 计划做 (e.g. 架构规划)
- 🔵 **紧急不重要**: 授权做 (e.g. 拿快递)
- ⚪ **不重要不紧急**: 减少做 (e.g. 琐事)

### 3. 🛡️ 企业级稳定性
- **进程守护**: 集成 **Supervisor**，崩溃自动重启。
- **开机自启**: 支持 macOS `launchd`，开机即用。
- **容错机制**: 
    - 消息去重 (防止重复创建任务)。
    - API 异常自动降级 (Filter 报错自动切换为内存过滤)。
    - 空消息/Help 指令拦截。
    - 防 `NoneType` 崩溃设计。

---

## 🛠 技术架构

- **语言**: Python 3.9+
- **框架**: `lark-oapi`, `openai`
- **进程管理**: `Supervisor`
- **存储**: 飞书多维表格 (Bitable)

### 文件结构
```
.
├── bot_ws.py           # 主程序：WebSocket 服务、事件分发、业务逻辑
├── llm_service.py      # AI 服务：封装 DeepSeek 调用，含 Prompt 优化
├── config.json         # (需自行创建) 配置文件：AppID, Secret, Token, LLM Key
├── supervisord.conf    # 进程守护配置
├── start.sh            # 一键启动脚本
├── stop.sh             # 一键停止脚本
├── install_autostart.sh # 开机自启安装脚本
└── logs/               # 运行日志
```

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
pip install supervisor
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

### 3. 启动服务
*   **前台运行**: `python3 bot_ws.py`
*   **后台守护 (推荐)**: `./start.sh`
*   **停止服务**: `./stop.sh`

### 4. 设置开机自启 (macOS)
```bash
./install_autostart.sh
```

## 📝 更新日志

### v2.3 (Current)
- **Feature**: 支持创建飞书原生任务 (Task V2)，且由 LLM 智能判断是否创建。
- **Fix**: 修复 `NoneType is not iterable` 偶发崩溃。
- **Fix**: 彻底解决机器人自指派问题 (三层过滤机制)。
- **Optimization**: 优化 Help 指令触发逻辑，支持空消息和关键词。

### v2.2
- **Stability**: 引入 Supervisor 和 macOS 开机自启。
- **Fix**: 修复 API Filter 报错，切换为全内存过滤。

### v2.0
- **Feature**: 引入 DeepSeek 大模型，支持四象限管理。