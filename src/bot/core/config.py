import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key

# Base Directory (Project Root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


def parse_instance_args():
    """Extract instance name and custom env file from sys.argv or environment variables."""
    instance_name = os.getenv("BOT_INSTANCE", "").strip()
    env_file_arg = os.getenv("BOT_ENV_FILE", "").strip()

    args = sys.argv[1:] if len(sys.argv) > 1 else []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--instance", "-i") and i + 1 < len(args):
            instance_name = args[i + 1].strip()
            i += 2
        elif arg.startswith("--instance="):
            instance_name = arg.split("=", 1)[1].strip()
            i += 1
        elif arg.startswith("-i="):
            instance_name = arg.split("=", 1)[1].strip()
            i += 1
        elif arg in ("--env", "-e") and i + 1 < len(args):
            env_file_arg = args[i + 1].strip()
            i += 2
        elif arg.startswith("--env="):
            env_file_arg = arg.split("=", 1)[1].strip()
            i += 1
        elif arg.startswith("-e="):
            env_file_arg = arg.split("=", 1)[1].strip()
            i += 1
    if not instance_name and env_file_arg:
        env_name = Path(env_file_arg).name
        if env_name.startswith(".env.") and len(env_name) > 5:
            instance_name = env_name[5:]
        elif env_name.endswith(".env") and env_name != ".env":
            instance_name = env_name[:-4]
        elif env_name != ".env":
            instance_name = Path(env_file_arg).stem

    return instance_name, env_file_arg


INSTANCE_NAME, CUSTOM_ENV = parse_instance_args()

if CUSTOM_ENV:
    ENV_FILE = Path(CUSTOM_ENV)
    if not ENV_FILE.is_absolute():
        ENV_FILE = BASE_DIR / ENV_FILE
elif INSTANCE_NAME:
    ENV_FILE = BASE_DIR / f".env.{INSTANCE_NAME}"
else:
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


def refresh_settings():
    """Reload settings from environment variables."""
    global BOT_TOKEN, ADMIN_IDS, PROXY_URL, DB_FILE, BACKUP_DIR, LOG_FILE, LOCK_FILE
    global MAX_RETRY_COUNT, DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX

    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS = get_admin_ids()
    PROXY_URL = os.getenv("PROXY_URL") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or None

    raw_db = os.getenv("DB_FILE", "").strip()
    raw_log = os.getenv("LOG_FILE", "").strip()
    raw_lock = os.getenv("LOCK_FILE", "").strip()
    raw_backup = os.getenv("BACKUP_DIR", "").strip()

    if INSTANCE_NAME:
        default_db = str(BASE_DIR / f"data/bot_{INSTANCE_NAME}.db")
        default_log = str(BASE_DIR / f"logs/bot_{INSTANCE_NAME}.log")
        default_lock = BASE_DIR / f"data/bot_{INSTANCE_NAME}.lock"
        default_backup = str(BASE_DIR / f"backups/{INSTANCE_NAME}")

        # If empty or using generic un-namespaced defaults, auto-isolate by instance name
        DB_FILE = default_db if (not raw_db or raw_db in ("data/bot.db", str(BASE_DIR / "data/bot.db"))) else raw_db
        LOG_FILE = default_log if (not raw_log or raw_log in ("logs/bot.log", str(BASE_DIR / "logs/bot.log"))) else raw_log
        LOCK_FILE = default_lock if (not raw_lock or raw_lock in ("data/bot.lock", str(BASE_DIR / "data/bot.lock"))) else Path(raw_lock)
        BACKUP_DIR = default_backup if (not raw_backup or raw_backup in ("backups", str(BASE_DIR / "backups"))) else raw_backup
    else:
        DB_FILE = raw_db or str(BASE_DIR / "data/bot.db")
        LOG_FILE = raw_log or str(BASE_DIR / "logs/bot.log")
        LOCK_FILE = Path(raw_lock) if raw_lock else (BASE_DIR / "data/bot.lock")
        BACKUP_DIR = raw_backup or str(BASE_DIR / "backups")

    MAX_RETRY_COUNT = int(os.getenv("MAX_RETRY_COUNT", "5"))
    DEFAULT_DELAY_MIN = int(os.getenv("DEFAULT_DELAY_MIN", "10"))
    DEFAULT_DELAY_MAX = int(os.getenv("DEFAULT_DELAY_MAX", "60"))


def ensure_config():
    """Ensure critical configuration exists, prompt user if missing."""
    global BOT_TOKEN, ADMIN_IDS
    
    if not ENV_FILE.exists():
        if (BASE_DIR / ".env.example").exists():
            import shutil
            shutil.copy(BASE_DIR / ".env.example", ENV_FILE)
            print(f"Created {ENV_FILE.name} from .env.example")
        else:
            ENV_FILE.touch()

    load_dotenv(ENV_FILE, override=True)
    refresh_settings()
    
    # Check BOT_TOKEN
    token = os.getenv("BOT_TOKEN")
    if not token or token == "your_bot_token_here":
        inst_label = f" for instance '{INSTANCE_NAME}'" if INSTANCE_NAME else ""
        print("\033[93m" + "!" * 50 + "\033[0m")
        print(f"\033[93mInvalid or Missing BOT_TOKEN{inst_label}!\033[0m")
        if sys.stdin.isatty():
            token = input(f"Please enter your Telegram Bot Token{inst_label} (from @BotFather): ").strip()
            if token:
                set_key(str(ENV_FILE), "BOT_TOKEN", token)
                os.environ["BOT_TOKEN"] = token
            else:
                print("Error: BOT_TOKEN is required to start the bot.")
                sys.exit(1)
        else:
            print(f"Error: Running in non-interactive mode with missing BOT_TOKEN. Please set it in {ENV_FILE.name} file.")
            sys.exit(1)
    
    BOT_TOKEN = token

    # Check ADMIN_IDS
    admins = os.getenv("ADMIN_IDS")
    if not admins or admins == "12345678,87654321":
        inst_label = f" for instance '{INSTANCE_NAME}'" if INSTANCE_NAME else ""
        print("\033[93m" + "!" * 50 + "\033[0m")
        print(f"\033[93mInvalid or Missing ADMIN_IDS{inst_label}!\033[0m")
        if sys.stdin.isatty():
            admins = input(f"Please enter Admin Telegram ID(s){inst_label} (comma separated): ").strip()
            if admins:
                set_key(str(ENV_FILE), "ADMIN_IDS", admins)
                os.environ["ADMIN_IDS"] = admins
            else:
                print("Warning: No ADMIN_IDS provided. System commands may be restricted.")
        else:
            print(f"Warning: Running in non-interactive mode with missing ADMIN_IDS in {ENV_FILE.name}.")
    
    refresh_settings()


# Initial load of paths and settings
refresh_settings()

# Constants
VERSION = "3.1.0"
SECONDS_IN_DAY = 86400
UPDATE_NOTES = """
- **Architectural Excellence**: Fully migrated to a standard `src/` modular layout.
- **Enhanced Deployment**: Python virtualenv and `pyproject.toml` support for seamless environments.
- **Optimized Forwarding**: Decoupled service/repository layer with transaction safety.
- **Multi-Instance Support**: Independent concurrent bots via --instance and isolated configs/databases.
"""

