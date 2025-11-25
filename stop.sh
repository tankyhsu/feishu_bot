#!/bin/bash

SUPERVISORCTL_BIN="$HOME/Library/Python/3.9/bin/supervisorctl"
if [ ! -f "$SUPERVISORCTL_BIN" ]; then
    SUPERVISORCTL_BIN="supervisorctl"
fi

echo "🛑 Stopping all services..."
"$SUPERVISORCTL_BIN" -c supervisord.conf stop all

echo "👋 Shutting down supervisor..."
"$SUPERVISORCTL_BIN" -c supervisord.conf shutdown
