import re
import logging
from typing import List
from telegram import MessageEntity
from src.bot.data.repositories import ChatRepository

logger = logging.getLogger(__name__)


def strip_hidden_chars(text: str) -> str:
    """Removes zero-width spaces and other invisible characters."""
    if not text:
        return ""
    # Zero-width space, Zero-width non-joiner, etc.
    chars = ["\u200b", "\u200c", "\u200d", "\ufeff"]
    for char in chars:
        text = text.replace(char, "")
    return text


async def clean_caption(
    text: str,
    chat_id: str,
    user_id: int = 0,
    entities: List[MessageEntity] = None,
    has_spoiler: bool = False,
    chat_title: str = "Unknown",
) -> str:
    """The main entry point for caption purification."""
    # 1. Fetch configuration
    rules = await ChatRepository.get_chat_rules(chat_id)
    keywords = await ChatRepository.get_keywords(chat_id)
    replacements = await ChatRepository.get_replacements(chat_id)
    footer = await ChatRepository.get_footer(chat_id)
    template = await ChatRepository.get_caption_template(chat_id)

    # 2. Preparation
    original_text = strip_hidden_chars(text or "")
    cleaned = original_text

    # 3. Execute cleaning pipeline

    # Remove links if clean_links rule is active
    if "clean_links" in rules:
        # Improved regex for links and @mentions
        cleaned = re.sub(r"http[s]?://\S+", "", cleaned)
        cleaned = re.sub(r"t\.me/\S+", "", cleaned)
        cleaned = re.sub(r"@\w+", "", cleaned)

    # Apply replacements
    for old, new in replacements:
        cleaned = cleaned.replace(old, new)

    # Apply keyword cleaning
    for word, is_regex in keywords:
        try:
            if is_regex:
                cleaned = re.sub(word, "", cleaned, flags=re.IGNORECASE)
            else:
                cleaned = cleaned.replace(word, "")
        except Exception as e:
            logger.warning(f"Invalid regex/keyword '{word}': {e}")

    cleaned = cleaned.strip()

    # 4. Apply Template if exists
    if template:
        from datetime import datetime

        vars = {
            "{orig}": cleaned,
            "{title}": chat_title,
            "{cid}": chat_id,
            "{date}": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "{user}": str(user_id) if user_id else "Unknown",
        }
        final_text = template
        for k, v in vars.items():
            final_text = final_text.replace(k, v)
        cleaned = final_text

    # 5. Add footer
    if footer:
        cleaned = f"{cleaned.strip()}\n\n{footer}"

    return cleaned.strip()


def restore_all_tags(original: str, cleaned: str) -> str:
    """Restores hashtags from original if missing."""
    tags = re.findall(r"#\w+", original)
    for tag in tags:
        if tag not in cleaned:
            cleaned += f" {tag}"
    return cleaned.strip()


async def check_spoiler_tags(text: str) -> bool:
    """Checks if any spoiler keywords are present."""
    # Simplified check for now
    return "#spoiler" in text.lower() or "#剧透" in text.lower()
