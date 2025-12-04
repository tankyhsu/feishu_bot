#!/bin/bash

# Use Venv Supervisor
SUPERVISORD_BIN="venv/bin/supervisord"
SUPERVISORCTL_BIN="venv/bin/supervisorctl"

echo "🚀 Starting Supervisor (Venv)..."
"$SUPERVISORD_BIN" -c supervisord.conf

echo "✅ Bot service started! Check status:"
"$SUPERVISORCTL_BIN" -c supervisord.conf status
