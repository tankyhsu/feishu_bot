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
- **智能任务创建**: 
    - 自动剔除 "提醒我"、"帮我建个任务" 等冗余词，提取核心任务名。
    - 示例: "提醒我八点吃药" -> 任务名: "八点吃药"。
- **语义任务更新**: 
    - 支持通过自然语言查找并操作任务，无需精确匹配任务名。
    - 示例: 用户说 "把那个修bug的任务关了"，机器人自动匹配到 "修复首页登录异常" 并完成。
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

## 部署 (Deployment)

本项目支持 macOS 本地部署，使用 `launchd` 进行进程守护和定时任务调度。

### 1. 自动部署

本项目提供了自动安装脚本，支持在任意目录下部署，脚本会自动识别当前路径并配置系统服务。

1.  **准备代码**
    将代码克隆到你希望部署的目录（建议使用用户主目录下的文件夹，例如 `~/feishu_bot`，以避免权限问题）：
    ```bash
    git clone https://github.com/your-repo/feishu_bot.git ~/feishu_bot
    cd ~/feishu_bot
    ```

2.  **创建环境**
    ```bash
    # 创建虚拟环境
    python3 -m venv venv
    
    # 安装依赖
    ./venv/bin/pip install -r requirements.txt
    
    # 安装 supervisor (用于进程守护)
    ./venv/bin/pip install supervisor
    ```

3.  **安装服务**
    直接运行安装脚本即可，无需手动修改配置文件路径：
    ```bash
    sh install_autostart.sh
    ```
    
    脚本会执行以下操作：
    *   自动识别当前项目路径。
    *   生成适配当前路径的系统配置文件 (`.plist`)。
    *   注册后台守护进程 (`com.feishu.bot.supervisor`)。
    *   注册每日定时推送任务 (`com.feishu.bot.daily_push`)。

### 2. 管理服务

*   **查看运行日志**：
    日志默认位于项目目录下的 `logs/` 文件夹中。
    ```bash
    # 查看主程序日志
    tail -f logs/bot_out.log logs/bot_err.log
    
    # 查看 Supervisor 守护进程日志
    tail -f logs/supervisord.log
    ```

*   **手动停止/重启**：
    可以使用提供的辅助脚本：
    ```bash
    sh stop.sh    # 停止服务
    sh start.sh   # 启动服务
    sh restart.sh # 重启服务
    ```

*   **卸载服务**：
    如果需要移除自动启动任务：
    ```bash
    launchctl unload ~/Library/LaunchAgents/com.feishu.bot.supervisor.plist
    launchctl unload ~/Library/LaunchAgents/com.feishu.bot.daily_push.plist
    rm ~/Library/LaunchAgents/com.feishu.bot.supervisor.plist
    rm ~/Library/LaunchAgents/com.feishu.bot.daily_push.plist
    ```

## 目录结构


## 📝 更新日志

### v2.6 (Current)
- **Fix**: 修复飞书原生任务 (Native Task) 创建失败的问题 (修正 `due.timestamp` 和 `role` 参数)。
- **Feature**: 增强时间解析能力，支持精确到小时分钟的截止时间 (e.g., "今晚八点吃药" -> `YYYY-MM-DD 20:00:00`)。
- **Optimization**: 优化 LLM Prompt，在上下文中注入当前精确时间，提升时间实体提取准确率。
- **Debug**: 增加任务创建接口的详细调试日志。

### v2.5
- **Feature**: 增强语义理解能力，支持自然语言查找和操作任务（Semantic Task Update）。
- **Optimization**: 优化任务创建 Prompt，自动提取核心任务名，剔除冗余指令词。
- **Fix**: 修复了服务初始化顺序和依赖注入问题。

### v2.4
- **Feature**: 新增 RSS 订阅服务，支持多源抓取。
- **Feature**: 新增自动生成飞书 RSS 早报文档功能 (Title + Summary + Link)。
- **Feature**: 新增 `scripts/daily_push.py` 用于定时推送。
- **Refactor**: 重构 `DocService`，支持更丰富的文档块操作。

### v2.3
- **Feature**: 支持创建飞书原生任务 (Task V2)。
- **Optimization**: 优化 AI 意图识别与负责人分配逻辑。
