import re
from telegram import MessageEntity
from db import get_keywords, get_rules, get_replacements, get_footer, is_user_whitelisted
from config import WHITELIST

LINK_REGEX = re.compile(r"(https?://[^\s]+|www\.[^\s]+|t\.me/[^\s]+)", re.IGNORECASE)
TG_MD_LINK_REGEX = re.compile(r"\[[^\]]+\]\((?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/[^\s)]+\)", re.IGNORECASE)
MD_LINK_REGEX = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", re.IGNORECASE)
AT_PREFIX_REGEX = re.compile(r"@\S+")
SPOILER_REGEX = re.compile(r'(#spoiler|#剧透|#nsfw)', re.IGNORECASE)
HASHTAG_REGEX = re.compile(r'(#[\w\u4e00-\u9fa5]+)', re.IGNORECASE)


def check_spoiler_tags(text: str) -> bool:
    if not text: return False
    return bool(SPOILER_REGEX.search(text))


def restore_all_tags(original_text: str, cleaned_text: str | None) -> str | None:
    if not original_text: return cleaned_text
    found_tags = HASHTAG_REGEX.findall(original_text)
    if not found_tags: return cleaned_text
    result = cleaned_text or ""
    existing = set(HASHTAG_REGEX.findall(result))
    missing = [tag for tag in found_tags if tag not in existing]
    if missing:
        result = (result + " " + " ".join(missing)).strip()
    return result or None


async def clean_caption(text: str | None, chat_id: str, user_id: int | None = None,
                        entities: list = None) -> str | None:
    text = text or ""
    if chat_id in WHITELIST: return text
    if user_id and await is_user_whitelisted(chat_id, str(user_id)): return text

    rules = await get_rules(chat_id)
    replacements = await get_replacements(chat_id)

    for old, new in replacements:
        text = text.replace(old, new)

    if "keep_all" in rules:
        pass
    else:
        has_entity_link = any(ent.type in [MessageEntity.TEXT_LINK, MessageEntity.URL] for ent in (entities or []))

        if "strip_all_if_links" in rules:
            if has_entity_link or LINK_REGEX.search(text) or MD_LINK_REGEX.search(text):
                text = ""

        if text and "clean_keywords" in rules:
            lines = []
            keywords = await get_keywords(chat_id)
            for line in text.splitlines():
                if not any((re.search(kw, line, re.IGNORECASE) if is_regex else kw.lower() in line.lower()) for
                           kw, is_regex in keywords):
                    lines.append(line)
            text = "\n".join(lines)

        if text and "block_keywords" in rules:
            keywords = await get_keywords(chat_id)
            if any((re.search(kw, text, re.IGNORECASE) if is_regex else kw.lower() in text.lower()) for kw, is_regex in
                   keywords):
                text = ""

        if text and "clean_links" in rules:
            text = TG_MD_LINK_REGEX.sub("", text)
            text = MD_LINK_REGEX.sub(r"\1", text)
            text = LINK_REGEX.sub("", text)

        if text and "remove_at_prefix" in rules:
            text = AT_PREFIX_REGEX.sub("", text)

        if text:
            for r in rules:
                if r.startswith("maxlen:"):
                    try:
                        maxlen = int(r.split(":")[1])
                        if len(text) > maxlen: text = ""
                    except:
                        pass
                    break

        if text:
            text = re.sub(r"\n{3,}", "\n\n", text).strip()

    footer = await get_footer(chat_id)
    if footer:
        text = f"{text}\n\n{footer}" if text else footer

    return text or None