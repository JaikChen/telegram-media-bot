import logging
from functools import wraps
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes
from src.bot.core.config import ADMIN_IDS
from src.bot.data.repositories import AdminRepository, ChatRepository, MediaRepository

logger = logging.getLogger(__name__)


def is_global_admin(user_id: int | str) -> bool:
    """Checks if the user is a super admin from config."""
    return int(user_id) in ADMIN_IDS


async def is_admin(update: Update) -> bool:
    """Checks if the sender/caller has bot administrative privileges (Global or dynamic)."""
    user = update.effective_user
    if not user:
        return False

    uid = str(user.id)
    if is_global_admin(uid):
        return True

    admins = await AdminRepository.list_admins()
    return uid in admins


async def check_chat_permission(user_id: int | str, chat_id: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if user has admin privileges in a specific chat."""
    if is_global_admin(user_id):
        return True

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ["creator", "administrator"]
    except Exception:
        return False


def admin_only(func):
    """[Decorator] Restricts command execution to bot admins."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not await is_admin(update):
            # We don't necessarily want to spam "no permission" for all commands
            return
        return await func(update, context, *args, **kwargs)

    return wrapper


def get_vote_markup(up_count: int, down_count: int) -> InlineKeyboardMarkup:
    """Generates the inline keyboard for voting."""
    keyboard = [
        [
            InlineKeyboardButton(f"👍 {up_count if up_count > 0 else ''}", callback_data="vote_up"),
            InlineKeyboardButton(f"👎 {down_count if down_count > 0 else ''}", callback_data="vote_down"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def escape_markdown(text: str) -> str:
    """Escapes characters for Telegram Markdown V1."""
    if not text:
        return ""
    escape_chars = r"_*`["
    return "".join(["\\" + char if char in escape_chars else char for char in text])


async def _delete_msg_job(context: ContextTypes.DEFAULT_TYPE):
    """Job callback to delete a message."""
    try:
        msg = context.job.data
        await msg.delete()
    except Exception as e:
        logger.warning(f"Failed to autodelete message: {e}")


async def reply_success(msg: Message, context: ContextTypes.DEFAULT_TYPE, text: str, chat_id: str | None = None):
    """Sends a success reply, respecting quiet mode and autodelete settings."""
    if not chat_id:
        await msg.reply_text(text, parse_mode="Markdown")
        return

    mode = await ChatRepository.get_quiet_mode(chat_id)
    if mode == "quiet":
        return

    try:
        sent_msg = await msg.reply_text(text, parse_mode="Markdown")
        if mode == "autodel" and context.job_queue:
            context.job_queue.run_once(_delete_msg_job, 10, data=sent_msg)
    except Exception as e:
        logger.warning(f"Failed to reply success: {e}")


async def log_event(bot: Bot, text: str, category: str = "system"):
    """Logs an event to the global log channel if configured."""
    try:
        log_cid = await MediaRepository.get_log_channel_global()
        if not log_cid:
            return

        # Log filter check (simplified for now)
        await bot.send_message(log_cid, f"<b>[{category.upper()}]</b>\n{text}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to log event: {e}")
