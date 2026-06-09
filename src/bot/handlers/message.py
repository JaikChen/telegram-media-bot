# handlers/message.py
"""
Handler for plain text messages, primarily used for keyword-based automatic replies.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from src.bot.data.repositories import ChatRepository

logger = logging.getLogger(__name__)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Process plain text messages and check for automatic reply triggers.

    Ignores commands (starting with '/') and messages in locked chats.
    """
    msg = update.message
    if not msg or not msg.text:
        return

    # Ignore commands
    if msg.text.startswith("/"):
        return

    chat_id = str(msg.chat_id)
    try:
        # Check if chat is locked
        if await ChatRepository.is_locked(chat_id):
            return

        # Fetch triggers for the chat
        triggers = await ChatRepository.get_triggers(chat_id)
        if not triggers:
            return

        content = msg.text.lower()
        # triggers is a list of tuples (word, text)
        for kw, reply_text in triggers:
            if kw in content:
                try:
                    await msg.reply_text(reply_text)
                    logger.info(f"Trigger hit: '{kw}' in chat {chat_id}")
                except Exception as e:
                    logger.warning(f"Failed to send trigger reply in chat {chat_id}: {e}")
                break
    except Exception as e:
        logger.error(f"Error in handle_text_message: {e}")
