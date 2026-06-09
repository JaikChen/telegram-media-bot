#!/bin/bash
# =================================================================
# Telegram Media Bot - Clean Reinstall Script
# =================================================================
# This script performs a destructive clean reinstall:
# 1. Backs up .env
# 2. Deletes EVERYTHING else (including database and logs)
# 3. Re-clones the repository from GitHub
# 4. Restores .env
# 5. Runs the deployment script
# =================================================================

set -e

REPO_URL="https://github.com/JaikChen/telegram-media-bot.git"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_PATH="$APP_DIR/../.env_bot_backup_$(date +%s)"

echo "--------------------------------------------------"
echo "🚀 Starting Clean Reinstall..."
echo "--------------------------------------------------"

# 1. Verify .env
if [ ! -f "$APP_DIR/.env" ]; then
    echo "❌ Error: .env file not found in $APP_DIR"
    echo "Aborting to prevent losing your configuration."
    exit 1
fi

# 2. Backup .env
echo "📦 Backing up .env to $BACKUP_PATH..."
cp "$APP_DIR/.env" "$BACKUP_PATH"

# 3. Clean directory
echo "🧹 Deleting all files in $APP_DIR..."
# We avoid deleting the script itself while it's running if possible, 
# but in bash, once the script is loaded, we can usually delete the file.
# To be safe, we move the backup outside first.

cd "$APP_DIR"
# Delete everything except the backup we just made (which is already outside)
# and possibly this script if we want to be extremely careful, but rm -rf * is fine.
find . -mindepth 1 -delete || rm -rf ./* ./.* 2>/dev/null || true

# 4. Re-clone
echo "📥 Re-cloning repository from $REPO_URL..."
git clone "$REPO_URL" .

# 5. Restore .env
echo "♻️ Restoring .env..."
mv "$BACKUP_PATH" "$APP_DIR/.env"

# 6. Run Deployment
echo "⚙️ Running scripts/deploy.sh..."
if [ -f "scripts/deploy.sh" ]; then
    chmod +x scripts/deploy.sh
    ./scripts/deploy.sh
else
    echo "❌ Error: scripts/deploy.sh not found after cloning!"
    exit 1
fi

echo "--------------------------------------------------"
echo "✅ Clean Reinstall Complete!"
echo "--------------------------------------------------"
