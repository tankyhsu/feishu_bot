#!/bin/bash

PLIST_NAME="com.feishu.bot.supervisor.plist"
DEST_DIR="$HOME/Library/LaunchAgents"
DEST_FILE="$DEST_DIR/$PLIST_NAME"

echo "🔧 配置开机自启 (Launchd)..."

# 1. 确保目录存在
mkdir -p "$DEST_DIR"

# 2. 如果服务已存在，先卸载 (方便更新配置)
if launchctl list | grep -q "com.feishu.bot.supervisor"; then
    echo "🔄 发现旧服务，正在卸载..."
    launchctl unload "$DEST_FILE" 2>/dev/null
fi

# 3. 复制 Plist 文件
echo "📂 复制配置文件到 $DEST_DIR..."
cp "$PLIST_NAME" "$DEST_DIR/"

# 4. 加载服务
echo "🚀 注册并启动服务..."
launchctl load "$DEST_FILE"

# 5. 验证
if launchctl list | grep -q "com.feishu.bot.supervisor"; then
    echo "✅ 开机自启配置成功！"
    echo "🤖 机器人现在已在后台运行，并且每次登录都会自动启动。"
    echo "📝 日志路径: logs/launchd.out"
else
    echo "❌ 配置失败，请检查报错信息。"
fi
