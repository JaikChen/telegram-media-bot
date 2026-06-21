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
PYTHON_EXE="python3"

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}==>${NC} $1"; }

# 1. Environment Check
check_environment() {
    log_step "Environment Self-Check"

    # 智能寻找可用的 Python 高版本解释器
    if command -v python3.11 &> /dev/null; then
        PYTHON_EXE="python3.11"
    elif command -v python3.10 &> /dev/null; then
        PYTHON_EXE="python3.10"
    elif command -v python3 &> /dev/null; then
        PYTHON_EXE="python3"
    else
        log_err "Python3 not found. Please install Python 3.10+"
        exit 1
    fi

    PY_MAJOR=$($PYTHON_EXE -c 'import sys; print(sys.version_info.major)')
    PY_MINOR=$($PYTHON_EXE -c 'import sys; print(sys.version_info.minor)')

    # 校验版本是否满足 >= 3.10
    if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
        log_err "Python version too low ($PY_MAJOR.$PY_MINOR) via '$PYTHON_EXE'. 3.10+ required."
        echo -e "${YELLOW}请尝试通过以下命令安装高版本 Python：${NC}"
        echo -e "  Ubuntu/Debian: ${BLUE}sudo apt install python3.10 python3.10-venv${NC}"
        echo -e "  CentOS/RHEL:   ${BLUE}sudo dnf install python310${NC} 或使用 ${BLUE}miniconda/pyenv${NC}"
        exit 1
    fi
    log_info "✅ Using Python Path: $(command -v $PYTHON_EXE) ($PY_MAJOR.$PY_MINOR)"

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

    # 如果虚拟环境不存在，或者之前的虚拟环境是用旧版本 Python 建立的，则强制重新创建
    if [ -d "$VENV_DIR" ]; then
        VENV_PY_MAJOR=$("$VENV_DIR/bin/python" -c 'import sys; print(sys.version_info.major)' 2>/dev/null || echo 0)
        VENV_PY_MINOR=$("$VENV_DIR/bin/python" -c 'import sys; print(sys.version_info.minor)' 2>/dev/null || echo 0)
        if [ "$VENV_PY_MAJOR" -lt 3 ] || { [ "$VENV_PY_MAJOR" -eq 3 ] && [ "$VENV_PY_MINOR" -lt 10 ]; }; then
            log_warn "Existing virtual environment uses an outdated Python ($VENV_PY_MAJOR.$VENV_PY_MINOR). Recreating..."
            rm -rf "$VENV_DIR"
        fi
    fi

    if [ ! -d "$VENV_DIR" ]; then
        log_warn "Creating virtual environment using $PYTHON_EXE..."
        $PYTHON_EXE -m venv "$VENV_DIR"
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

        # Cleanup existing bot processes
        log_info "Cleaning up existing bot processes..."
        if command -v pkill &> /dev/null; then
            pkill -f "python src/main.py" || true
        else
            log_warn "pkill not found. Skipping process cleanup."
        fi
        sleep 2

        log_info "Attempting to start bot..."
        if command -v nohup &> /dev/null; then
            nohup "$VENV_DIR/bin/python" src/main.py > "$APP_DIR/logs/bot.log" 2>&1 &
            log_info "✅ Bot started in background (PID: $!)."
        else
            log_info "nohup not found. Starting bot in foreground (press Ctrl+C to stop)."
            "$VENV_DIR/bin/python" src/main.py
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