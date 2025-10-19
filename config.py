import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot 的令牌
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 从环境变量中加载管理员 ID，并转换为集合
ADMIN_IDS = set(os.getenv("ADMIN_IDS", "").split(","))

# SQLite 数据库文件路径
DB_FILE = "bot.db"

# 白名单频道/用户（不清理说明）
WHITELIST = {
    # 示例："-1001234567890", "987654321"
}