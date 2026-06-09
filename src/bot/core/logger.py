import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler
from colorama import Fore, Style, init as colorama_init
from src.bot.core.config import LOG_FILE

colorama_init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        log_color = self.COLORS.get(record.levelno, "")
        format_str = f"{Fore.WHITE}%(asctime)s{Style.RESET_ALL} - {log_color}%(levelname)-8s{Style.RESET_ALL} - {Fore.MAGENTA}%(name)s{Style.RESET_ALL} - %(message)s"
        formatter = logging.Formatter(format_str, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)

    # Ensure log directory exists
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    file_handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", interval=1, backupCount=30, encoding="utf-8")
    file_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # Silence noise
    for log_name in ["httpx", "httpcore", "telegram.ext.AIORateLimiter"]:
        logging.getLogger(log_name).setLevel(logging.WARNING)

    return logger
