# 飞书智能项目管理机器人 (Dobby) - v2.4

基于飞书集成平台与 DeepSeek 大模型的智能助手，集成了**智能任务管理**、**会议纪要生成**与**RSS 新闻早报**三大核心能力，打造全能型团队助理。

## 🌟 核心功能

### 1. 📰 RSS 新闻早报 (New!)
- **多源聚合**: 支持配置多个 RSS 订阅源 (TechCrunch, Hacker News 等)。
- **AI 智能总结**: 每天定时抓取最新文章，利用 DeepSeek 进行去重、分类和一句话总结。
- **精美文档生成**: 自动生成图文并茂的飞书云文档（含标题、摘要、原文链接），排版整洁美观。
- **群组推送**: 
    - **被动触发**: 在群里发送 "RSS" 或 "早报" 即可立即获取。
    - **定时推送**: 支持 launchd 定时任务，每天早晨准时推送早报文档链接。

### 2. 🧠 AI 语义理解 (DeepSeek)
- **自然语言创建**: "帮我安排明天修一下首页Bug，挺急的" -> 自动识别任务、时间、紧急程度。
- **智能负责人分配**: 自动识别 `@提及` 的成员并分配任务，智能排除机器人自己。
- **原生任务联动**: 仅当用户提到 "提醒我"、"建个任务" 时，同步创建飞书原生 Task (Task V2)。

### 3. 📝 会议纪要助手
- **妙记解析**: 发送飞书妙记链接，机器人自动抓取字幕。
- **AI 提炼**: 自动总结会议摘要、Action Items，并生成飞书云文档归档。

### 4. 📊 四象限任务管理
采用科学的时间管理法则 (Eisenhower Matrix)，自动标记任务优先级 (重要且紧急等)。

---

## 🛠 技术架构

- **语言**: Python 3.9+
- **框架**: `lark-oapi`, `feedparser`
- **AI 模型**: DeepSeek V3
- **进程管理**: `Supervisor` (通过 `launchd` 管理)
- **数据存储**: 飞书多维表格 (Bitable) + 飞书云文档 (Docx)

### 文件结构
```
.
├── main.py             # 主程序入口
├── config.py           # 配置加载器
├── handlers/           # 消息与事件处理器
├── services/           # 核心服务层
│   ├── llm_service.py  # AI 服务 (DeepSeek)
│   ├── rss_service.py  # RSS 抓取与文档生成
│   ├── doc_service.py  # 飞书文档操作 (Block 构建)
│   └── ...
├── scripts/            # 工具脚本
│   └── daily_push.py   # 定时推送脚本
└── supervisord.conf    # 进程守护配置
```

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置 `config.json`
在项目根目录创建 `config.json`：
```json
{
  "APP_ID": "cli_xxx",
  "APP_SECRET": "xxx",
  "BITABLE_APP_TOKEN": "xxx",
  "TABLE_ID": "xxx",
  "LLM_API_KEY": "sk-xxx",
  "LLM_BASE_URL": "https://api.deepseek.com",
  "LLM_MODEL": "deepseek-chat",
  "DAILY_PUSH_CHAT_ID": "oc_xxx",  // 接收早报的群ID
  "FEEDS": [
    {
      "name": "TechCrunch",
      "url": "https://techcrunch.com/feed/",
      "category": "🚀 科技前沿"
    }
  ]
}
```

### 3. 启动与定时任务
macOS 用户可直接运行安装脚本，一键完成主程序守护和定时任务的配置。

*   **一键安装/启动 (后台守护)**: `./install_autostart.sh`
*   **手动启动 (前台调试)**: `./start.sh`
*   **停止服务**: `./stop.sh`
*   **重启服务**: `./restart.sh`

`install_autostart.sh` 会自动配置 `launchd` 服务，实现：
1.  **机器人主进程守护**: 确保 `main.py` 持续在后台运行。
2.  **RSS 早报定时推送**: 每天上午 10 点自动执行 `scripts/daily_push.py`。


## 📝 更新日志

### v2.4 (Current)
- **Feature**: 新增 RSS 订阅服务，支持多源抓取。
- **Feature**: 新增自动生成飞书 RSS 早报文档功能 (Title + Summary + Link)。
- **Feature**: 新增 `scripts/daily_push.py` 用于定时推送。
- **Refactor**: 重构 `DocService`，支持更丰富的文档块操作。

### v2.3
- **Feature**: 支持创建飞书原生任务 (Task V2)。
- **Optimization**: 优化 AI 意图识别与负责人分配逻辑。
