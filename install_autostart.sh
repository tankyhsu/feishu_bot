#!/bin/bash

# 获取脚本所在的绝对路径作为项目根目录
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DEST_DIR="$HOME/Library/LaunchAgents"

echo "📂 检测到项目目录: $PROJECT_DIR"

# --- Function to set up a launchd service ---
setup_service() {
    local plist_name=$1
    local service_label=$(basename "$plist_name" .plist)
    local dest_file="$DEST_DIR/$plist_name"

    echo "---"
    echo "🔧 配置服务: $service_label"

    # 1. Unload existing service
    if launchctl list | grep -q "$service_label"; then
        echo "🔄 Unloading existing service..."
        launchctl unload "$dest_file" 2>/dev/null
    fi

    # 2. Process and copy plist
    # Replace __PROJECT_DIR__ with actual path and save to destination
    echo "📝 Generating config with path: $PROJECT_DIR"
    sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PROJECT_DIR/$plist_name" > "$dest_file"

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

# Setup services
setup_service "com.feishu.bot.supervisor.plist"
setup_service "com.feishu.bot.daily_push.plist"

echo "---"
echo "✅ 所有服务配置完成!"
echo "🤖 服务已绑定到目录: $PROJECT_DIR"