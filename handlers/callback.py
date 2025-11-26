# handlers/callback.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from db import get_vote_counts, get_user_vote, add_vote, remove_vote


def get_vote_markup(up: int, down: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"👍 {up}", callback_data="vote_up"),
        InlineKeyboardButton(f"👎 {down}", callback_data="vote_down")
    ]])


async def handle_vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    msg = query.message
    if not msg: await query.answer("❌ 消息已失效"); return

    chat_id = str(msg.chat_id)
    msg_id = str(msg.message_id)
    data = query.data
    if not data.startswith("vote_"): await query.answer(); return

    target_type = data.split("_")[1]
    current_vote = get_user_vote(chat_id, msg_id, user_id)

    if current_vote == target_type:
        remove_vote(chat_id, msg_id, user_id)
        await query.answer("已取消投票")
    else:
        add_vote(chat_id, msg_id, user_id, target_type)
        await query.answer("投票成功")

    up, down = get_vote_counts(chat_id, msg_id)
    try:
        await query.edit_message_reply_markup(reply_markup=get_vote_markup(up, down))
    except Exception:
        pass