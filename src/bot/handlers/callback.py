# handlers/callback.py
"""
Callback query handlers for interactive elements like voting buttons.
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from src.bot.data.repositories import VoteRepository

logger = logging.getLogger(__name__)


def get_vote_markup(up: int, down: int) -> InlineKeyboardMarkup:
    """
    Generate the inline keyboard markup for voting.

    Args:
        up: Number of upvotes.
        down: Number of downvotes.

    Returns:
        InlineKeyboardMarkup: The markup with up and down buttons.
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"👍 {up}", callback_data="vote_up"),
                InlineKeyboardButton(f"👎 {down}", callback_data="vote_down"),
            ]
        ]
    )


async def handle_vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle voting callbacks from media messages.

    This function processes 'vote_up' and 'vote_down' callbacks,
    updating the database and the message's reply markup.
    """
    query = update.callback_query
    if not query:
        return

    user = query.from_user
    uid = str(user.id)
    msg = query.message
    if not msg:
        return

    cid, mid = str(msg.chat_id), str(msg.message_id)
    data = query.data
    if not data or not data.startswith("vote_"):
        return

    try:
        target = data.split("_")[1]  # up / down
        current = await VoteRepository.get_user_vote(cid, mid, uid)

        if current == target:
            await VoteRepository.remove_vote(cid, mid, uid)
            await query.answer("已取消投票")
            logger.info(f"User {uid} removed vote from msg {mid} in chat {cid}")
        else:
            await VoteRepository.add_vote(cid, mid, uid, target)
            await query.answer("投票成功")
            logger.info(f"User {uid} voted {target} on msg {mid} in chat {cid}")

        up, down = await VoteRepository.get_vote_counts(cid, mid)
        await query.edit_message_reply_markup(reply_markup=get_vote_markup(up, down))

    except Exception as e:
        logger.error(f"Error handling vote callback: {e}")
        await query.answer("操作失败，请稍后重试", show_alert=True)
