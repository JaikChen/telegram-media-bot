import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key

# Base Directory (Project Root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

# Load .env immediately
if ENV_FILE.exists():
    load_dotenv(ENV_FILE, override=True)

# Bot Settings
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = []
PROXY_URL = os.getenv("PROXY_URL") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or None


def get_admin_ids():
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)
    raw_combined = f"{os.getenv('ADMIN_IDS', '')},{os.getenv('ADMIN_ID', '')}"
    admin_ids = []
    for part in raw_combined.replace(" ", ",").replace(";", ",").split(","):
        clean_part = part.strip().strip("'").strip('"')
        if clean_part:
            try:
                admin_ids.append(int(clean_part))
            except ValueError:
                pass
    return sorted(list(set(admin_ids)))


def add_admin_id(new_id: int):
    """Adds a new admin ID to memory and persists to .env file."""
    global ADMIN_IDS
    ADMIN_IDS = get_admin_ids()
    if new_id not in ADMIN_IDS:
        ADMIN_IDS.append(new_id)
        ADMIN_IDS.sort()
        admin_str = ",".join(str(i) for i in ADMIN_IDS)
        try:
            if not ENV_FILE.exists():
                ENV_FILE.touch()
            set_key(str(ENV_FILE), "ADMIN_ID", admin_str)
            set_key(str(ENV_FILE), "ADMIN_IDS", admin_str)
            os.environ["ADMIN_ID"] = admin_str
            os.environ["ADMIN_IDS"] = admin_str
        except Exception as e:
            print("Error persisting ADMIN_ID to .env:", e)


def remove_admin_id(target_id: int):
    """Removes an admin ID from memory and persists to .env file."""
    global ADMIN_IDS
    ADMIN_IDS = get_admin_ids()
    if target_id in ADMIN_IDS:
        ADMIN_IDS.remove(target_id)
        admin_str = ",".join(str(i) for i in ADMIN_IDS)
        try:
            if not ENV_FILE.exists():
                ENV_FILE.touch()
            set_key(str(ENV_FILE), "ADMIN_ID", admin_str)
            set_key(str(ENV_FILE), "ADMIN_IDS", admin_str)
            os.environ["ADMIN_ID"] = admin_str
            os.environ["ADMIN_IDS"] = admin_str
        except Exception as e:
            print("Error updating ADMIN_ID in .env:", e)


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
        if sys.stdin.isatty():
            token = input("Please enter your Telegram Bot Token (from @BotFather): ").strip()
            if token:
                set_key(str(ENV_FILE), "BOT_TOKEN", token)
                os.environ["BOT_TOKEN"] = token
            else:
                print("Error: BOT_TOKEN is required to start the bot.")
                sys.exit(1)
        else:
            print("Error: Running in non-interactive mode with missing BOT_TOKEN. Please set it in .env file.")
            sys.exit(1)
    
    BOT_TOKEN = token

    # Check ADMIN_IDS
    admins = os.getenv("ADMIN_IDS")
    if not admins or admins == "12345678,87654321":
        print("\033[93m" + "!" * 50 + "\033[0m")
        print("\033[93mInvalid or Missing ADMIN_IDS!\033[0m")
        if sys.stdin.isatty():
            admins = input("Please enter Admin Telegram ID(s) (comma separated): ").strip()
            if admins:
                set_key(str(ENV_FILE), "ADMIN_IDS", admins)
                os.environ["ADMIN_IDS"] = admins
            else:
                print("Warning: No ADMIN_IDS provided. System commands may be restricted.")
        else:
            print("Warning: Running in non-interactive mode with missing ADMIN_IDS.")
    
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
- **Enhanced Deployment**: Python virtualenv and `pyproject.toml` support for seamless environments.
- **Optimized Forwarding**: Decoupled service/repository layer with transaction safety.
"""

