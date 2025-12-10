#!/bin/bash

TARGET_DIR="$HOME/feishu_bot"
DEST_DIR="$HOME/Library/LaunchAgents"

# --- Function to set up a launchd service ---
setup_service() {
    local plist_name=$1
    local service_label=$(basename "$plist_name" .plist)
    local dest_file="$DEST_DIR/$plist_name"

    echo "---"
    echo "🔧 配置服务: $service_label"

    # 1. Unload existing
    if launchctl list | grep -q "$service_label"; then
        echo "🔄 Unloading existing service..."
        launchctl unload "$dest_file" 2>/dev/null
    fi

    # 2. Copy plist from TARGET directory (where we deployed it)
    echo "📂 Copying plist to $DEST_DIR"
    cp "$TARGET_DIR/$plist_name" "$DEST_DIR/"

    # 3. Load
    echo "🚀 Loading new service..."
    launchctl load "$dest_file"

    # 4. Verify
    if launchctl list | grep -q "$service_label"; then
        echo "✅ Service '$service_label' is now loaded."
    else
        echo "❌ Failed to load service '$service_label'. Please check logs."
    fi
}

echo "🚀 开始配置飞书机器人 (用户目录模式)..."
# Ensure target dir exists (should already be there from previous steps)
mkdir -p "$TARGET_DIR"

# Install supervisor in the target venv if not present
if [ ! -f "$TARGET_DIR/venv/bin/supervisord" ]; then
    echo "⬇️ Installing supervisor in target venv..."
    "$TARGET_DIR/venv/bin/pip" install supervisor --quiet
fi

# Sync configuration files from current dir to target dir
echo "📂 Syncing configuration files..."
cp supervisord.conf config.py com.feishu.bot.supervisor.plist com.feishu.bot.daily_push.plist "$TARGET_DIR/"

# Setup services
setup_service "com.feishu.bot.supervisor.plist"
setup_service "com.feishu.bot.daily_push.plist"

echo "---"
echo "✅ 迁移完成!"
echo "📂 项目目录: $TARGET_DIR"
echo "📝 日志目录: $TARGET_DIR/logs"
