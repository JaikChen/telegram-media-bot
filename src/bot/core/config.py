import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base Directory (Project Root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Bot Settings
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(i) for i in os.getenv("ADMIN_IDS", "").split(",") if i]

# Storage Settings
DB_FILE = os.getenv("DB_FILE", str(BASE_DIR / "data/bot.db"))
BACKUP_DIR = os.getenv("BACKUP_DIR", str(BASE_DIR / "backups"))
LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "logs/bot.log"))

# Forwarding Settings
MAX_RETRY_COUNT = int(os.getenv("MAX_RETRY_COUNT", "5"))
DEFAULT_DELAY_MIN = int(os.getenv("DEFAULT_DELAY_MIN", "10"))
DEFAULT_DELAY_MAX = int(os.getenv("DEFAULT_DELAY_MAX", "60"))

# Constants
VERSION = "3.1.0"
SECONDS_IN_DAY = 86400
UPDATE_NOTES = """
- **Architectural Excellence**: Fully migrated to a standard `src/` modular layout.
- **Enhanced Deployment**: Full Docker and `pyproject.toml` support for seamless environments.
- **Optimized Forwarding**: Decoupled service/repository layer with transaction safety.
"""
