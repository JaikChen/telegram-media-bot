# config.py
# 用于加载环境变量和配置管理员权限

import os
from dotenv import load_dotenv

# 加载 .env 文件中的 BOT_TOKEN
load_dotenv()

# Telegram Bot 的令牌
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 固定管理员用户 ID 集合（仅这些用户可使用私聊命令）
# 同时还支持数据库动态管理员（见 db.py）
ADMIN_IDS = {
    "8383577888",  # 主
    "7622430663",  # 备用
    "8477598792"   # 创造
}

# SQLite 数据库文件路径
DB_FILE = "bot.db"

# 白名单频道/用户（不清理说明）
WHITELIST = {
    # 示例："-1001234567890", "987654321"
}