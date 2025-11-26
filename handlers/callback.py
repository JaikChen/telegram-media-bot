# handlers/callback.py
# 处理按钮点击回调 (投票系统)

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from db import get_vote_counts, get_user_vote, add_vote, remove_vote


def get_vote_markup(up: int, down: int):
    """生成带有当前票数的按钮"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"👍 {up}", callback_data="vote_up"),
            InlineKeyboardButton(f"👎 {down}", callback_data="vote_down")
        ]
    ])


async def handle_vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理投票点击事件"""
    query = update.callback_query
    user_id = str(query.from_user.id)
    msg = query.message

    # 某些情况下 message 可能为空（如消息太久远），做个保护
    if not msg:
        await query.answer("❌ 消息已失效")
        return

    chat_id = str(msg.chat_id)
    msg_id = str(msg.message_id)

    # callback_data 格式: "vote_up" 或 "vote_down"
    data = query.data
    if not data.startswith("vote_"):
        await query.answer()
        return

    target_type = data.split("_")[1]  # 'up' or 'down'

    # 获取用户之前的投票状态
    current_vote = get_user_vote(chat_id, msg_id, user_id)

    if current_vote == target_type:
        # 点击了相同的按钮 -> 取消投票
        remove_vote(chat_id, msg_id, user_id)
        await query.answer("已取消投票")
    else:
        # 点击了不同按钮 -> 更新/新增投票
        add_vote(chat_id, msg_id, user_id, target_type)
        await query.answer("投票成功")

    # 获取最新票数
    up, down = get_vote_counts(chat_id, msg_id)
    new_markup = get_vote_markup(up, down)

    # 更新按钮显示 (如果数字没变，Telegram 会抛错，忽略即可)
    try:
        await query.edit_message_reply_markup(reply_markup=new_markup)
    except Exception:
        pass