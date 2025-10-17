#!/bin/bash

# 一键更新 Telegram Media Bot 脚本
# 作者：一悲

set -e

REPO_URL="https://github.com/JaikChen/telegram-media-bot.git"
BOT_DIR="/opt/telegram-media-bot"
SERVICE_NAME="telegram-media-bot"

echo "🚀 开始更新 Telegram Media Bot..."

# 停止服务
echo "🛑 停止服务：$SERVICE_NAME"
sudo systemctl stop $SERVICE_NAME

# 如果目录不存在则克隆，否则拉取更新
if [ ! -d "$BOT_DIR" ]; then
    echo "📦 克隆仓库到 $BOT_DIR"
    sudo git clone $REPO_URL $BOT_DIR
else
    echo "🔄 拉取最新代码..."
    cd $BOT_DIR
    sudo git reset --hard
    # 使用合并方式拉取，避免 fast-forward 错误
    sudo git pull --no-rebase || {
        echo "❌ Git 拉取失败，可能存在冲突，请手动解决后重新运行脚本。"
        exit 1
    }
fi

# 进入目录并更新依赖
cd $BOT_DIR
echo "📥 更新依赖..."
source .venv/bin/activate
pip install -r requirements.txt

# 重启服务
echo "▶️ 重启服务：$SERVICE_NAME"
sudo systemctl start $SERVICE_NAME

echo "✅ 更新完成！Bot 已重新启动。"