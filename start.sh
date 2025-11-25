#!/bin/bash

# 1. 获取 Python bin 路径 (Supervisor 安装位置)
SUPERVISORD_BIN="$HOME/Library/Python/3.9/bin/supervisord"
SUPERVISORCTL_BIN="$HOME/Library/Python/3.9/bin/supervisorctl"

# 检查是否存在，不存在尝试直接调用 (如果已在PATH)
if [ ! -f "$SUPERVISORD_BIN" ]; then
    SUPERVISORD_BIN="supervisord"
    SUPERVISORCTL_BIN="supervisorctl"
fi

echo "🚀 Starting Supervisor..."
"$SUPERVISORD_BIN" -c supervisord.conf

echo "✅ Bot service started! Check status:"
"$SUPERVISORCTL_BIN" -c supervisord.conf status
