# 飞书机器人项目进度记录

## ✅ 已完成功能 (2025-11-24)

### 1. 核心逻辑
- **指令解析**: 支持自然语言解析任务名、负责人、优先级 (高/中/低, 支持大小写)、截止日期。
- **数据写入**: 成功对接飞书多维表格 (Bitable) API，支持文本、单选、人员、日期字段写入。
- **WebSocket 模式**: 使用 `lark-oapi` 的 WebSocket 客户端，无需公网 IP 即可接收群消息。

### 2. 环境配置
- **Python**: 3.9+
- **依赖**: `lark-oapi`, `requests`
- **配置文件**: `config.json` (存储 App ID 和 Secret)

### 3. 多维表格配置
- **文件 Token**: `DR8mbUoyUazoQ9sk0VTcB5sLnkh`
- **数据表 ID**: `tbl01oWhlWFaEQsk`
- **字段映射**:
  - `任务描述` (多行文本) <- 解析出的任务名
  - `优先级` (单选) <- High/Medium/Low
  - `负责人` (人员) <- @的用户
  - `截止日期` (日期) <- YYYY-MM-DD

## 🚀 如何启动

1. **安装依赖**:
   ```bash
   pip install -r requirements.txt
   ```

2. **配置**:
   确保 `config.json` 存在且包含正确的 `APP_ID` 和 `APP_SECRET`。

3. **运行**:
   ```bash
   python3 bot_ws.py
   ```

4. **测试指令**:
   在飞书群中发送: `@机器人 修复首页Bug 高 2025-12-31 @张三`

## ⚠️ 注意事项
- **权限**: 机器人必须是多维表格的 **"可编辑" (Editor)** 协作者。
- **字段名**: 代码中硬编码了字段名 "任务描述"，如表格结构变更需同步修改代码。
