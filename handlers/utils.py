import re
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from db import list_admins, get_quiet_mode, get_log_channel, get_log_filter


def is_global_admin(user_id: str | int) -> bool:
    return str(user_id) in ADMIN_IDS


async def is_admin(msg):
    if not msg or not msg.from_user: return False
    uid = str(msg.from_user.id)
    if is_global_admin(uid): return True
    # 本地管理员缓存检查，减少DB压力
    return uid in list_admins()


async def check_chat_permission(user_id: int | str, chat_id: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """检查用户是否具有该群组的管理权限"""
    uid = str(user_id)
    if is_global_admin(uid): return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception:
        return False


async def reply_success(msg, context: ContextTypes.DEFAULT_TYPE, text: str, chat_id: str = None):
    """根据静音模式回复"""
    if not chat_id:
        await msg.reply_text(text, parse_mode="Markdown")
        return
    mode = get_quiet_mode(chat_id)
    if mode == "quiet": return

    try:
        sent_msg = await msg.reply_text(text, parse_mode="Markdown")
        if mode == "autodel" and context.job_queue:
            context.job_queue.run_once(lambda ctx: ctx.job.data.delete(), 10, data=sent_msg)
    except Exception:
        pass


async def log_event(bot, text: str, category: str = "system"):
    """发送日志"""
    allowed_types = get_log_filter()
    if category not in allowed_types: return

    log_channel = get_log_channel()
    if not log_channel: return

    prefix = {
        "clean": "♻️ [清理]", "duplicate": "🗑 [去重]",
        "forward": "↪️ [转发]", "error": "⚠️ [错误]", "system": "⚙️ [系统]"
    }.get(category, "")

    try:
        await bot.send_message(chat_id=log_channel, text=f"{prefix} {text}")
    except:
        pass


def escape_markdown(text: str) -> str:
    if not text: return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(text))