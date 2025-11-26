# handlers/utils.py
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from db import list_admins, get_quiet_mode

def is_global_admin(user_id: str | int) -> bool:
    return str(user_id) in ADMIN_IDS

async def is_admin(msg):
    uid = str(msg.from_user.id)
    if is_global_admin(uid): return True
    return uid in list_admins()

async def check_chat_permission(user_id: int | str, chat_id: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    uid = str(user_id)
    if is_global_admin(uid): return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception: return False

async def delete_msg_job(context: ContextTypes.DEFAULT_TYPE):
    try: await context.job.data.delete()
    except Exception: pass

async def reply_success(msg, context: ContextTypes.DEFAULT_TYPE, text: str, chat_id: str = None):
    target_chat_id = chat_id if chat_id else str(msg.chat_id)
    if not chat_id:
        await msg.reply_text(text, parse_mode="Markdown")
        return
    mode = get_quiet_mode(chat_id)
    if mode == "quiet": return
    sent_msg = await msg.reply_text(text, parse_mode="Markdown")
    if mode == "autodel" and context.job_queue:
        context.job_queue.run_once(delete_msg_job, 10, data=sent_msg)