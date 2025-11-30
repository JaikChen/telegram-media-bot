# handlers/message.py
# 纯文本消息处理（自动回复）

from telegram import Update
from telegram.ext import ContextTypes
from db import get_triggers, is_locked

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text: return
    if msg.text.startswith("/"): return # 忽略命令

    chat_id = str(msg.chat_id)
    if is_locked(chat_id): return

    triggers = get_triggers(chat_id)
    if not triggers: return

    content = msg.text.lower()
    for kw, reply_text in triggers.items():
        if kw in content:
            try: await msg.reply_text(reply_text)
            except: pass
            break