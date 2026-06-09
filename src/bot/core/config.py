import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key

# Base Directory (Project Root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

# Bot Settings
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = []

def get_admin_ids():
    return [int(i) for i in os.getenv("ADMIN_IDS", "").split(",") if i]

def ensure_config():
    """Ensure critical configuration exists, prompt user if missing."""
    global BOT_TOKEN, ADMIN_IDS
    
    if not ENV_FILE.exists():
        if (BASE_DIR / ".env.example").exists():
            import shutil
            shutil.copy(BASE_DIR / ".env.example", ENV_FILE)
            print(f"Created .env from .env.example")
        else:
            ENV_FILE.touch()

    load_dotenv(ENV_FILE, override=True)
    
    # Check BOT_TOKEN
    token = os.getenv("BOT_TOKEN")
    if not token or token == "your_bot_token_here":
        print("\033[93m" + "!" * 50 + "\033[0m")
        print("\033[93mInvalid or Missing BOT_TOKEN!\033[0m")
        token = input("Please enter your Telegram Bot Token (from @BotFather): ").strip()
        if token:
            set_key(str(ENV_FILE), "BOT_TOKEN", token)
            os.environ["BOT_TOKEN"] = token
        else:
            print("Error: BOT_TOKEN is required to start the bot.")
            sys.exit(1)
    
    BOT_TOKEN = token

    # Check ADMIN_IDS
    admins = os.getenv("ADMIN_IDS")
    if not admins or admins == "12345678,87654321":
        print("\033[93m" + "!" * 50 + "\033[0m")
        print("\033[93mInvalid or Missing ADMIN_IDS!\033[0m")
        admins = input("Please enter Admin Telegram ID(s) (comma separated): ").strip()
        if admins:
            set_key(str(ENV_FILE), "ADMIN_IDS", admins)
            os.environ["ADMIN_IDS"] = admins
        else:
            print("Warning: No ADMIN_IDS provided. System commands may be restricted.")
    
    ADMIN_IDS = get_admin_ids()

# Initial load
ADMIN_IDS = get_admin_ids()

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
