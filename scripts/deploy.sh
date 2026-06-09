#!/bin/bash
# =================================================================
# Telegram Media Bot - Ultimate Update & Deployment Script
# =================================================================
# This script ensures the local environment is consistent with GitHub
# by syncing code, dependencies, and restarting the service.
# =================================================================

set -e

# Color definitions
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="telegram-media-bot"

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}==>${NC} $1"; }

# 1. Environment Check
check_environment() {
    log_step "Environment Self-Check"
    
    if ! command -v python3 &> /dev/null; then
        log_err "python3 not found. Please install Python 3.10+"
        exit 1
    fi
    
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    # Compare versions using a simple string comparison or bc
    if [ "$(echo "$PY_VERSION < 3.10" | bc -l)" -eq 1 ]; then
        log_err "Python version too low ($PY_VERSION). 3.10+ required."
        exit 1
    fi
    log_info "✅ Python Version: $PY_VERSION"

    if ! command -v git &> /dev/null; then
        log_err "git not found. Cannot update code from GitHub."
        exit 1
    fi

    if [ ! -f "$APP_DIR/.env" ]; then
        log_warn ".env file missing! Bot will not start without BOT_TOKEN."
        if [ -f "$APP_DIR/.env.example" ]; then
            log_info "Creating .env from .env.example..."
            cp "$APP_DIR/.env.example" "$APP_DIR/.env"
        fi
    fi
}

# 2. Sync Code with GitHub
sync_code() {
    log_step "Syncing Code with GitHub"
    
    if [ -d "$APP_DIR/.git" ]; then
        log_info "Fetching latest changes..."
        git fetch --all --prune
        
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
        log_info "Current branch: $CURRENT_BRANCH"
        
        # Discard local changes and untracked files to ensure consistency
        log_warn "Discarding local changes and untracked files..."
        git reset --hard "origin/$CURRENT_BRANCH"
        git clean -fd
        
        log_info "✅ Code sync complete."
    else
        log_err "Not a git repository. Skip code sync."
    fi
}

# 3. Update Dependencies
update_deps() {
    log_step "Updating Dependencies"
    
    if [ ! -d "$VENV_DIR" ]; then
        log_warn "Virtual environment missing. Creating..."
        python3 -m venv "$VENV_DIR"
    fi
    
    # Activate venv
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
    elif [ -f "$VENV_DIR/Scripts/activate" ]; then
        source "$VENV_DIR/Scripts/activate"
    fi
    
    log_info "Upgrading pip and installing requirements..."
    pip install --upgrade pip --quiet
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt --quiet
        log_info "Verifying dependencies..."
        pip check || log_warn "Dependency conflicts detected (pip check)."
    elif [ -f "pyproject.toml" ]; then
        pip install . --quiet
        log_info "Installed from pyproject.toml"
    else
        log_err "Neither requirements.txt nor pyproject.toml found!"
        exit 1
    fi
    log_info "✅ Dependencies updated."
}

# 4. Restart Service
restart_bot() {
    log_step "Restarting Service"
    
    # Ensure directories exist
    mkdir -p "$APP_DIR/data" "$APP_DIR/logs" "$APP_DIR/backups"
    
    if command -v systemctl &> /dev/null && systemctl is-active --quiet "$SERVICE_NAME"; then
        log_info "Restarting systemd service: $SERVICE_NAME"
        sudo systemctl restart "$SERVICE_NAME"
        log_info "✅ Service restarted via systemd."
    else
        log_warn "Service $SERVICE_NAME is not active or not installed as a systemd service."
        
        # Windows compatibility or non-systemd Linux
        log_info "Cleaning up existing bot processes..."
        if command -v pkill &> /dev/null; then
            pkill -f "python src/main.py" || true
        else
            log_warn "pkill not found. Skipping process cleanup."
        fi
        sleep 2
        
        log_info "Attempting to start bot..."
        if command -v nohup &> /dev/null; then
            nohup python src/main.py > "$APP_DIR/logs/bot.log" 2>&1 &
            log_info "✅ Bot started in background (PID: $!)."
        else
            log_info "nohup not found. Starting bot in foreground (press Ctrl+C to stop)."
            python src/main.py
        fi
    fi
}

# Main Execution
main() {
    echo -e "${BLUE}==================================================${NC}"
    echo -e "${BLUE}   Telegram Media Bot Update Script (Ultimate)   ${NC}"
    echo -e "${BLUE}==================================================${NC}"
    
    check_environment
    sync_code
    update_deps
    restart_bot
    
    echo -e "${BLUE}==================================================${NC}"
    log_info "🎉 Update Completed Successfully!"
    log_info "Check logs with: journalctl -u $SERVICE_NAME -f"
    echo -e "${BLUE}==================================================${NC}"
}

main
