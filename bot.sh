#!/usr/bin/env bash
# ==============================================================================
# Telegram Media Bot - Linux 综合管理脚本 (Multi-Instance Manager)
# ==============================================================================
# 支持功能:
#   1. 启动 / 停止 / 重启 (支持 Bot 1、Bot 2 或 全部)
#   2. 添加 / 配置 Bot 1 和 Bot 2 (向导式配置 Token、管理员与代理)
#   3. 从 GitHub 一键更新项目与依赖，并自动平滑重启
#   4. 查看实时运行状态、内存占用、数据库大小及实时日志
#   5. 一键注册 / 管理 systemd 系统守护进程服务
# ==============================================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

PID_DIR="$APP_DIR/.run"
mkdir -p "$PID_DIR" "$APP_DIR/data" "$APP_DIR/logs" "$APP_DIR/backups"

VENV_PYTHON="$APP_DIR/.venv/bin/python"

# 基础打印函数
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${CYAN}==>${NC} $1"; }

# 检查 Python 与虚拟环境
check_venv() {
    if [ ! -f "$VENV_PYTHON" ]; then
        log_warn "未检测到虚拟环境，正在初始化环境..."
        if [ -f "$APP_DIR/install.sh" ]; then
            bash "$APP_DIR/install.sh"
        elif [ -f "$APP_DIR/scripts/deploy.sh" ]; then
            bash "$APP_DIR/scripts/deploy.sh"
        else
            python3 -m venv "$APP_DIR/.venv"
            "$VENV_PYTHON" -m pip install --upgrade pip
            if [ -f "$APP_DIR/requirements.txt" ]; then
                "$VENV_PYTHON" -m pip install -r "$APP_DIR/requirements.txt"
            fi
        fi
    fi
}

# 辅助函数: 获取指定 Bot 的运行 PID (返回 0 表示未运行)
get_bot_pid() {
    local target="$1"
    local pid=""
    if [ "$target" = "bot1" ]; then
        # 匹配无 --instance 的主 bot
        pid=$(pgrep -f "src/main.py$" 2>/dev/null | head -n 1 || true)
    elif [ "$target" = "bot2" ]; then
        # 匹配 --instance bot2
        pid=$(pgrep -f "src/main.py --instance bot2" 2>/dev/null | head -n 1 || true)
    fi

    # 如果 pgrep 未找到，尝试检查 PID 文件
    if [ -z "$pid" ] && [ -f "$PID_DIR/${target}.pid" ]; then
        local saved_pid
        saved_pid=$(cat "$PID_DIR/${target}.pid" 2>/dev/null || true)
        if [ -n "$saved_pid" ] && kill -0 "$saved_pid" 2>/dev/null; then
            pid="$saved_pid"
        else
            rm -f "$PID_DIR/${target}.pid"
        fi
    fi

    echo "$pid"
}

# 启动单个 Bot
start_single_bot() {
    local target="$1"
    check_venv

    local pid
    pid=$(get_bot_pid "$target")
    if [ -n "$pid" ]; then
        log_warn "[$target] 已经在运行中 (PID: $pid)。"
        return 0
    fi

    if [ "$target" = "bot1" ]; then
        if [ ! -f "$APP_DIR/.env" ]; then
            log_err "[$target] 配置文件 .env 不存在！请先选择配置 Bot 1。"
            return 1
        fi
        log_step "正在启动主机器人 (Bot 1)..."
        nohup "$VENV_PYTHON" src/main.py >> "$APP_DIR/logs/bot.log" 2>&1 &
        local new_pid=$!
        echo "$new_pid" > "$PID_DIR/bot1.pid"
        sleep 2
        if kill -0 "$new_pid" 2>/dev/null; then
            log_info "✅ [Bot 1] 启动成功 (PID: $new_pid)！日志: logs/bot.log"
        else
            log_err "❌ [Bot 1] 启动失败，请检查日志: tail -n 20 logs/bot.log"
        fi
    elif [ "$target" = "bot2" ]; then
        if [ ! -f "$APP_DIR/.env.bot2" ]; then
            log_err "[$target] 配置文件 .env.bot2 不存在！请先选择配置 Bot 2。"
            return 1
        fi
        log_step "正在启动第二个机器人 (Bot 2)..."
        nohup "$VENV_PYTHON" src/main.py --instance bot2 >> "$APP_DIR/logs/bot_bot2.log" 2>&1 &
        local new_pid=$!
        echo "$new_pid" > "$PID_DIR/bot2.pid"
        sleep 2
        if kill -0 "$new_pid" 2>/dev/null; then
            log_info "✅ [Bot 2] 启动成功 (PID: $new_pid)！日志: logs/bot_bot2.log"
        else
            log_err "❌ [Bot 2] 启动失败，请检查日志: tail -n 20 logs/bot_bot2.log"
        fi
    fi
}

# 停止单个 Bot
stop_single_bot() {
    local target="$1"
    local pid
    pid=$(get_bot_pid "$target")

    if [ -z "$pid" ]; then
        log_warn "[$target] 未处于运行状态。"
        rm -f "$PID_DIR/${target}.pid"
        return 0
    fi

    log_step "正在停止 [$target] (PID: $pid)..."
    kill "$pid" 2>/dev/null || true
    local count=0
    while kill -0 "$pid" 2>/dev/null && [ "$count" -lt 5 ]; do
        sleep 1
        count=$((count + 1))
    done

    if kill -0 "$pid" 2>/dev/null; then
        log_warn "[$target] 进程未响应，正在强制终止 (SIGKILL)..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_DIR/${target}.pid"
    if [ "$target" = "bot1" ]; then
        rm -f "$APP_DIR/data/bot.lock"
    elif [ "$target" = "bot2" ]; then
        rm -f "$APP_DIR/data/bot_bot2.lock"
    fi
    log_info "✅ [$target] 已停止。"
}

# 重启单个 Bot
restart_single_bot() {
    local target="$1"
    log_step "正在重启 [$target]..."
    stop_single_bot "$target"
    sleep 1
    start_single_bot "$target"
}

# 启动全量
start_all() {
    log_step "正在启动所有已配置的 Bot..."
    if [ -f "$APP_DIR/.env" ]; then
        start_single_bot "bot1"
    else
        log_warn "未检测到 .env，跳过 Bot 1"
    fi
    if [ -f "$APP_DIR/.env.bot2" ]; then
        start_single_bot "bot2"
    else
        log_warn "未检测到 .env.bot2，跳过 Bot 2"
    fi
}

# 停止全量
stop_all() {
    log_step "正在停止所有 Bot..."
    stop_single_bot "bot1"
    stop_single_bot "bot2"
}

# 重启全量
restart_all() {
    log_step "正在重启所有 Bot..."
    stop_all
    sleep 1
    start_all
}

# 查看运行状态
show_status() {
    echo -e "\n${BLUE}========================= 运行状态监控 =========================${NC}"
    printf "%-8s | %-10s | %-8s | %-10s | %-18s\n" "Bot" "状态" "PID" "内存占用" "数据库"
    echo "----------------------------------------------------------------"

    # Bot 1
    local pid1
    pid1=$(get_bot_pid "bot1")
    if [ -n "$pid1" ]; then
        local mem1
        mem1=$(ps -p "$pid1" -o rss= 2>/dev/null | awk '{printf "%.1f MB", $1/1024}' || echo "N/A")
        local db1="N/A"
        [ -f "$APP_DIR/data/bot.db" ] && db1=$(du -h "$APP_DIR/data/bot.db" | cut -f1)
        printf "%-8s | ${GREEN}%-10s${NC} | %-8s | %-10s | %-18s\n" "Bot 1" "运行中" "$pid1" "$mem1" "bot.db ($db1)"
    else
        printf "%-8s | ${RED}%-10s${NC} | %-8s | %-10s | %-18s\n" "Bot 1" "未运行" "-" "-" "bot.db"
    fi

    # Bot 2
    local pid2
    pid2=$(get_bot_pid "bot2")
    if [ -n "$pid2" ]; then
        local mem2
        mem2=$(ps -p "$pid2" -o rss= 2>/dev/null | awk '{printf "%.1f MB", $1/1024}' || echo "N/A")
        local db2="N/A"
        [ -f "$APP_DIR/data/bot_bot2.db" ] && db2=$(du -h "$APP_DIR/data/bot_bot2.db" | cut -f1)
        printf "%-8s | ${GREEN}%-10s${NC} | %-8s | %-10s | %-18s\n" "Bot 2" "运行中" "$pid2" "$mem2" "bot_bot2.db ($db2)"
    else
        printf "%-8s | ${RED}%-10s${NC} | %-8s | %-10s | %-18s\n" "Bot 2" "未运行" "-" "-" "bot_bot2.db"
    fi

    echo -e "${BLUE}================================================================${NC}\n"
}

# 配置 / 添加 Bot 1
setup_bot1() {
    echo -e "\n${CYAN}--- [配置 Bot 1 (.env)] ---${NC}"
    if [ ! -f "$APP_DIR/.env" ] && [ -f "$APP_DIR/.env.example" ]; then
        cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    fi

    echo -e "${YELLOW}请输入 Bot 1 的 Token (从 @BotFather 获取):${NC}"
    read -r token
    if [ -n "$token" ]; then
        sed -i "s/^BOT_TOKEN=.*/BOT_TOKEN=$token/" "$APP_DIR/.env" || echo "BOT_TOKEN=$token" >> "$APP_DIR/.env"
    fi

    echo -e "${YELLOW}请输入管理员 Telegram ID (多个逗号隔开，直接回车保留默认):${NC}"
    read -r admins
    if [ -n "$admins" ]; then
        sed -i "s/^ADMIN_IDS=.*/ADMIN_IDS=$admins/" "$APP_DIR/.env" || echo "ADMIN_IDS=$admins" >> "$APP_DIR/.env"
    fi

    echo -e "${YELLOW}请输入代理地址 (例如 socks5://127.0.0.1:7891，无代理直接回车):${NC}"
    read -r proxy
    if [ -n "$proxy" ]; then
        sed -i "s|^PROXY_URL=.*|PROXY_URL=$proxy|" "$APP_DIR/.env" || echo "PROXY_URL=$proxy" >> "$APP_DIR/.env"
    fi

    log_info "✅ Bot 1 配置已更新保存至 .env"
}

# 配置 / 添加 Bot 2
setup_bot2() {
    echo -e "\n${CYAN}--- [配置 Bot 2 (.env.bot2)] ---${NC}"
    if [ ! -f "$APP_DIR/.env.bot2" ]; then
        if [ -f "$APP_DIR/.env.bot2.example" ]; then
            cp "$APP_DIR/.env.bot2.example" "$APP_DIR/.env.bot2"
        elif [ -f "$APP_DIR/.env.example" ]; then
            cp "$APP_DIR/.env.example" "$APP_DIR/.env.bot2"
        fi
    fi

    echo -e "${YELLOW}请输入 Bot 2 的 Token (从 @BotFather 获取):${NC}"
    read -r token
    if [ -n "$token" ]; then
        sed -i "s/^BOT_TOKEN=.*/BOT_TOKEN=$token/" "$APP_DIR/.env.bot2" || echo "BOT_TOKEN=$token" >> "$APP_DIR/.env.bot2"
    fi

    echo -e "${YELLOW}请输入管理员 Telegram ID (直接回车同步 Bot 1 配置):${NC}"
    read -r admins
    if [ -n "$admins" ]; then
        sed -i "s/^ADMIN_IDS=.*/ADMIN_IDS=$admins/" "$APP_DIR/.env.bot2" || echo "ADMIN_IDS=$admins" >> "$APP_DIR/.env.bot2"
    elif [ -f "$APP_DIR/.env" ]; then
        local env_admins
        env_admins=$(grep "^ADMIN_IDS=" "$APP_DIR/.env" | cut -d'=' -f2-)
        [ -n "$env_admins" ] && sed -i "s/^ADMIN_IDS=.*/ADMIN_IDS=$env_admins/" "$APP_DIR/.env.bot2"
    fi

    echo -e "${YELLOW}请输入代理地址 (直接回车同步 Bot 1 配置):${NC}"
    read -r proxy
    if [ -n "$proxy" ]; then
        sed -i "s|^PROXY_URL=.*|PROXY_URL=$proxy|" "$APP_DIR/.env.bot2" || echo "PROXY_URL=$proxy" >> "$APP_DIR/.env.bot2"
    elif [ -f "$APP_DIR/.env" ]; then
        local env_proxy
        env_proxy=$(grep "^PROXY_URL=" "$APP_DIR/.env" | cut -d'=' -f2-)
        [ -n "$env_proxy" ] && sed -i "s|^PROXY_URL=.*|PROXY_URL=$env_proxy|" "$APP_DIR/.env.bot2"
    fi

    log_info "✅ Bot 2 配置已更新保存至 .env.bot2"
}

# 更新项目代码与依赖
update_project() {
    log_step "正在从 GitHub 拉取最新代码..."
    if [ -d "$APP_DIR/.git" ]; then
        git fetch --all --prune
        local branch
        branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "master")
        log_info "当前分支: $branch"
        git stash || true
        git pull origin "$branch"
        log_info "✅ 代码已同步到最新版本。"
    else
        log_err "当前目录不是 git 仓库，无法执行自动拉取。"
        return 1
    fi

    log_step "正在检查并更新依赖包..."
    check_venv
    "$VENV_PYTHON" -m pip install --upgrade pip --quiet
    if [ -f "$APP_DIR/requirements.txt" ]; then
        "$VENV_PYTHON" -m pip install -r "$APP_DIR/requirements.txt" --quiet
    fi
    log_info "✅ 依赖包更新完成。"

    echo -e "${YELLOW}是否立即重启正在运行的机器人？(y/n)${NC}"
    read -r ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        restart_all
    fi
}

# 查看日志
view_logs() {
    echo -e "${YELLOW}请选择要查看的日志:${NC}"
    echo "1) Bot 1 日志 (logs/bot.log)"
    echo "2) Bot 2 日志 (logs/bot_bot2.log)"
    read -r choice
    case "$choice" in
        1)
            [ -f "$APP_DIR/logs/bot.log" ] && tail -f -n 50 "$APP_DIR/logs/bot.log" || log_err "日志文件不存在。"
            ;;
        2)
            [ -f "$APP_DIR/logs/bot_bot2.log" ] && tail -f -n 50 "$APP_DIR/logs/bot_bot2.log" || log_err "日志文件不存在。"
            ;;
        *)
            log_warn "无效选项。"
            ;;
    esac
}

# 安装 Systemd 守护服务
install_systemd() {
    if ! command -v systemctl &> /dev/null; then
        log_err "当前系统不支持 systemd。"
        return 1
    fi

    local cur_user
    cur_user=$(whoami)
    log_step "为当前用户 ($cur_user) 安装 systemd 服务..."

    # Bot 1 服务
    sudo tee /etc/systemd/system/telegram-bot1.service > /dev/null <<EOF
[Unit]
Description=Telegram Media Bot (Bot 1)
After=network.target

[Service]
Type=simple
User=$cur_user
WorkingDirectory=$APP_DIR
ExecStart=$VENV_PYTHON src/main.py
Restart=always
RestartSec=5
StandardOutput=append:$APP_DIR/logs/bot.log
StandardError=append:$APP_DIR/logs/bot.log

[Install]
WantedBy=multi-user.target
EOF

    # Bot 2 服务
    sudo tee /etc/systemd/system/telegram-bot2.service > /dev/null <<EOF
[Unit]
Description=Telegram Media Bot (Bot 2)
After=network.target

[Service]
Type=simple
User=$cur_user
WorkingDirectory=$APP_DIR
ExecStart=$VENV_PYTHON src/main.py --instance bot2
Restart=always
RestartSec=5
StandardOutput=append:$APP_DIR/logs/bot_bot2.log
StandardError=append:$APP_DIR/logs/bot_bot2.log

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable telegram-bot1.service telegram-bot2.service
    log_info "✅ Systemd 服务创建完成: telegram-bot1.service & telegram-bot2.service"
    log_info "你可以使用以下命令管理: sudo systemctl start/restart/status telegram-bot1"
}

# 交互式菜单
show_menu() {
    while true; do
        echo -e "${PURPLE}====================================================${NC}"
        echo -e "${PURPLE}   🤖 Telegram Media Bot - Linux 服务管理终端   ${NC}"
        echo -e "${PURPLE}====================================================${NC}"
        echo -e " ${GREEN}1)${NC} 启动全部 Bot (Bot 1 + Bot 2)"
        echo -e " ${GREEN}2)${NC} 重启全部 Bot"
        echo -e " ${RED}3)${NC} 停止全部 Bot"
        echo -e "----------------------------------------------------"
        echo -e " ${CYAN}4)${NC} 启动单个 Bot (可指定 Bot 1 / Bot 2)"
        echo -e " ${CYAN}5)${NC} 重启单个 Bot (可指定 Bot 1 / Bot 2)"
        echo -e " ${CYAN}6)${NC} 停止单个 Bot (可指定 Bot 1 / Bot 2)"
        echo -e "----------------------------------------------------"
        echo -e " ${YELLOW}7)${NC} 查看运行状态 (PID / 内存 / 数据库)"
        echo -e " ${YELLOW}8)${NC} 查看实时运行日志"
        echo -e "----------------------------------------------------"
        echo -e " ${BLUE}9)${NC} 配置 / 添加 Bot 1 (.env)"
        echo -e " ${BLUE}10)${NC} 配置 / 添加 Bot 2 (.env.bot2)"
        echo -e " ${BLUE}11)${NC} 从 GitHub 一键更新项目与依赖"
        echo -e " ${BLUE}12)${NC} 注册并配置 Systemd 守护服务 (开机自启)"
        echo -e "----------------------------------------------------"
        echo -e " ${RED}0)${NC} 退出脚本"
        echo -e "${PURPLE}====================================================${NC}"
        read -p "请输入操作序号 [0-12]: " opt

        case "$opt" in
            1) start_all ;;
            2) restart_all ;;
            3) stop_all ;;
            4)
                echo "1) 启动 Bot 1   2) 启动 Bot 2"
                read -r s_opt
                [ "$s_opt" = "1" ] && start_single_bot "bot1"
                [ "$s_opt" = "2" ] && start_single_bot "bot2"
                ;;
            5)
                echo "1) 重启 Bot 1   2) 重启 Bot 2"
                read -r s_opt
                [ "$s_opt" = "1" ] && restart_single_bot "bot1"
                [ "$s_opt" = "2" ] && restart_single_bot "bot2"
                ;;
            6)
                echo "1) 停止 Bot 1   2) 停止 Bot 2"
                read -r s_opt
                [ "$s_opt" = "1" ] && stop_single_bot "bot1"
                [ "$s_opt" = "2" ] && stop_single_bot "bot2"
                ;;
            7) show_status ;;
            8) view_logs ;;
            9) setup_bot1 ;;
            10) setup_bot2 ;;
            11) update_project ;;
            12) install_systemd ;;
            0) exit 0 ;;
            *) log_warn "输入无效，请重新选择。" ;;
        esac
        echo ""
    done
}

# 命令行直接调用参数处理
case "$1" in
    start)
        if [ "$2" = "bot1" ]; then start_single_bot "bot1";
        elif [ "$2" = "bot2" ]; then start_single_bot "bot2";
        else start_all; fi
        ;;
    stop)
        if [ "$2" = "bot1" ]; then stop_single_bot "bot1";
        elif [ "$2" = "bot2" ]; then stop_single_bot "bot2";
        else stop_all; fi
        ;;
    restart)
        if [ "$2" = "bot1" ]; then restart_single_bot "bot1";
        elif [ "$2" = "bot2" ]; then restart_single_bot "bot2";
        else restart_all; fi
        ;;
    status)
        show_status
        ;;
    update)
        update_project
        ;;
    logs)
        if [ "$2" = "bot2" ]; then
            tail -f -n 50 "$APP_DIR/logs/bot_bot2.log"
        else
            tail -f -n 50 "$APP_DIR/logs/bot.log"
        fi
        ;;
    add|setup)
        if [ "$2" = "bot2" ]; then setup_bot2; else setup_bot1; fi
        ;;
    systemd)
        install_systemd
        ;;
    help|--help|-h)
        echo "用法: $0 [start|stop|restart|status|update|logs|add|systemd] [bot1|bot2|all]"
        ;;
    "")
        show_menu
        ;;
    *)
        log_err "未知参数: $1。运行 '$0 help' 查看使用帮助。"
        exit 1
        ;;
esac
