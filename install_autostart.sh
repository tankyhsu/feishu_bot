#!/bin/bash

DEST_DIR="$HOME/Library/LaunchAgents"

# --- Function to set up a launchd service ---
setup_service() {
    local plist_name=$1
    local service_label=$(basename "$plist_name" .plist)
    local dest_file="$DEST_DIR/$plist_name"

    echo "---"
    echo "🔧 配置服务: $service_label"

    # 1. If service exists, unload it first for a clean update
    if launchctl list | grep -q "$service_label"; then
        echo "🔄 Unloading existing service..."
        launchctl unload "$dest_file" 2>/dev/null
    fi

    # 2. Copy the plist file
    echo "📂 Copying plist to $DEST_DIR"
    cp "$plist_name" "$DEST_DIR/"

    # 3. Load the service
    echo "🚀 Loading new service..."
    launchctl load "$dest_file"

    # 4. Verify
    if launchctl list | grep -q "$service_label"; then
        echo "✅ Service '$service_label' is now loaded."
    else
        echo "❌ Failed to load service '$service_label'. Please check logs."
    fi
}

# --- Main Script ---

echo "🚀 开始配置飞书机器人后台服务 (launchd)..."

# Ensure the target directory exists
mkdir -p "$DEST_DIR"

# Setup the main bot supervisor service
setup_service "com.feishu.bot.supervisor.plist"

# Setup the daily push scheduled task
setup_service "com.feishu.bot.daily_push.plist"

echo "---"
echo "✅ 所有服务配置完成!"
echo "🤖 机器人主进程将在后台运行，每日推送任务已设定。"
