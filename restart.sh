#!/bin/bash

echo "🔄 Restarting Dobby..."

# 1. Stop
./stop.sh

# 2. Wait a sec
sleep 2

# 3. Start
./start.sh

echo "✅ Restart complete."
