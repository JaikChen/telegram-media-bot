#!/bin/bash
# =================================================================
# Telegram Media Bot - One-Click Installation Script
# =================================================================
# This script automates the entire setup process for a new server:
# 1. Installs system dependencies (Python, Git, etc.)
# 2. Configures the environment (.env)
# 3. Sets up the virtual environment and dependencies
# 4. Configures systemd for auto-restart
# =================================================================

set -e

# Color definitions
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_step() { echo -e "${BLUE}==>${NC} $1"; }
log_err() { echo -e "${RED}[ERROR]${NC} $1"; }

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="telegram-media-bot"

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}      Telegram Media Bot - One-Click Setup      ${NC}"
echo -e "${BLUE}==================================================${NC}"

# 1. Install System Dependencies
log_step "Installing System Dependencies"
if command -v apt-get &> /dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3 python3-venv git curl bc > /dev/null
    log_info "✅ System dependencies installed."
else
    log_info "⚠️ Non-Debian system detected. Please ensure python3, venv, and git are installed."
fi

# 2. Setup .env
log_step "Configuring Environment"
if [ ! -f "$APP_DIR/.env" ]; then
    if [ -f "$APP_DIR/.env.example" ]; then
        cp "$APP_DIR/.env.example" "$APP_DIR/.env"
        log_info "Created .env from .env.example"
        
        echo -e "${YELLOW}Please provide your Bot Token (from @BotFather):${NC}"
        read -r BOT_TOKEN
        if [ -n "$BOT_TOKEN" ]; then
            sed -i "s/BOT_TOKEN=.*/BOT_TOKEN=$BOT_TOKEN/" "$APP_DIR/.env"
        fi
        
        echo -e "${YELLOW}Please provide your Telegram User ID (for Admin):${NC}"
        read -r ADMIN_ID
        if [ -n "$ADMIN_ID" ]; then
            sed -i "s/ADMIN_ID=.*/ADMIN_ID=$ADMIN_ID/" "$APP_DIR/.env"
        fi
    else
        log_err ".env.example not found! Manual configuration required."
    fi
else
    log_info "✅ .env file already exists."
fi

# 3. Run Deployment Script
log_step "Running Deployment"
chmod +x "$APP_DIR/scripts/deploy.sh"
bash "$APP_DIR/scripts/deploy.sh"

# 4. Optional: Systemd Service Setup
log_step "Systemd Integration"
if [ ! -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
    echo -e "${YELLOW}Would you like to install the bot as a systemd service? (y/n)${NC}"
    read -r INSTALL_SERVICE
    if [[ "$INSTALL_SERVICE" =~ ^[Yy]$ ]]; then
        USER_NAME=$(whoami)
        cat <<EOF | sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null
[Unit]
Description=Telegram Media Bot
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python src/main.py
Restart=always
RestartSec=10
StandardOutput=append:$APP_DIR/logs/bot.log
StandardError=append:$APP_DIR/logs/bot.log

[Install]
WantedBy=multi-user.target
EOF
        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE_NAME"
        sudo systemctl start "$SERVICE_NAME"
        log_info "✅ Systemd service installed and started."
    fi
else
    log_info "✅ Systemd service already exists."
fi

echo -e "${BLUE}==================================================${NC}"
log_info "🎉 Installation Complete!"
echo -e "Check status: ${BLUE}systemctl status $SERVICE_NAME${NC}"
echo -e "View logs: ${BLUE}tail -f logs/bot.log${NC}"
echo -e "${BLUE}==================================================${NC}"
