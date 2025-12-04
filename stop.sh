#!/bin/bash

SUPERVISORCTL_BIN="venv/bin/supervisorctl"

echo "🛑 Stopping all services..."
"$SUPERVISORCTL_BIN" -c supervisord.conf stop all

echo "👋 Shutting down supervisor..."
"$SUPERVISORCTL_BIN" -c supervisord.conf shutdown
