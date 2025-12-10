import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 基础路径
BASE_DIR = Path(__file__).parent.resolve()

# Telegram Bot 的令牌
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ 未在 .env 文件中设置 BOT_TOKEN")

# 管理员 ID 集合 (自动去重/去空)
_admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {x.strip() for x in _admin_ids_str.split(",") if x.strip()}

# 数据库文件路径
DB_FILE = BASE_DIR / "bot.db"

# 白名单配置
WHITELIST = set()  # 可在代码中扩展或从文件加载