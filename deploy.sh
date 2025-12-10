#!/bin/bash
SRC_DIR="/Users/txu35/Documents/tools/feishu_bot"
DEST_DIR="/Users/txu35/Library/Application Support/feishu_bot/app"
VENV_DIR="/Users/txu35/Library/Application Support/feishu_bot/venv"

echo "📦 Deploying to $DEST_DIR..."

# 1. Sync files (excluding heavy/unnecessary dirs)
rsync -av --exclude 'venv' --exclude '.git' --exclude '__pycache__' --exclude 'logs' --delete "$SRC_DIR/" "$DEST_DIR/"

# 2. Setup Venv if not exists
if [ ! -d "$VENV_DIR" ]; then
    echo "🐍 Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# 3. Install requirements
echo "⬇️ Installing requirements..."
"$VENV_DIR/bin/pip" install -r "$DEST_DIR/requirements.txt" --quiet

echo "✅ Deployment complete."
