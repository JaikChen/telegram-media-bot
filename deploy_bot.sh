#!/bin/bash
set -e

APP_DIR="/opt/telegram-media-bot"
VENV_DIR="$APP_DIR/.venv"
SERVICE_FILE="/etc/systemd/system/telegram-media-bot.service"

echo "🚀 开始部署 Telegram Bot..."

# 进入项目目录
cd $APP_DIR

# 如果已有旧虚拟环境，删除
if [ -d "$VENV_DIR" ]; then
  echo "🧹 删除旧虚拟环境..."
  rm -rf $VENV_DIR
fi

# 创建新虚拟环境
echo "📦 创建虚拟环境..."
python3.11 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# 升级 pip 并安装依赖
echo "📥 安装依赖..."
pip install --upgrade pip
pip install python-telegram-bot==20.7 python-dotenv

# 检查 .env 文件是否存在
if [ ! -f "$APP_DIR/.env" ]; then
  echo "⚠️ 未找到 .env 文件，请创建并写入 BOT_TOKEN"
  exit 1
fi

# 创建 systemd 服务文件
echo "📝 创建 systemd 服务..."
sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Telegram Media Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/python $APP_DIR/main.py
EnvironmentFile=$APP_DIR/.env
Restart=always
RestartSec=5
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF

# 重新加载 systemd
echo "🔄 重新加载 systemd..."
sudo systemctl daemon-reload

# 启用并启动服务
echo "▶️ 启动服务..."
sudo systemctl enable telegram-media-bot
sudo systemctl restart telegram-media-bot

echo "✅ 部署完成！使用以下命令查看日志："
echo "   journalctl -u telegram-media-bot -f"
