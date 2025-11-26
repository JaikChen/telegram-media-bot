# cleaner.py
import re
from telegram import MessageEntity
from db import get_keywords, get_rules, get_replacements, get_footer, is_user_whitelisted
from config import WHITELIST

LINK_REGEX = re.compile(r"(https?://[^\s]+|www\.[^\s]+|t\.me/[^\s]+)", re.IGNORECASE)
MD_LINK_REGEX = re.compile(r"\[[^\]]+\]\((https?://[^\s)]+)\)", re.IGNORECASE)
AT_PREFIX_REGEX = re.compile(r"@\S+")


def _parse_maxlen(rules: list[str]) -> int | None:
    for r in rules:
        if r.startswith("maxlen:"):
            try:
                return int(r.split(":", 1)[1])
            except ValueError:
                return None
    return None


def clean_caption(text: str | None, chat_id: str, user_id: str | int | None = None,
                  entities: list = None) -> str | None:
    text = text or ""

    if chat_id in WHITELIST: return text.strip() or None
    if user_id and is_user_whitelisted(chat_id, str(user_id)): return text.strip() or None

    rules = get_rules(chat_id)
    replacements = get_replacements(chat_id)
    if replacements:
        for old, new in replacements: text = text.replace(old, new)

    if "keep_all" in rules:
        pass
    else:
        has_entity_link = False
        if entities:
            for ent in entities:
                if ent.type in [MessageEntity.TEXT_LINK, MessageEntity.URL]:
                    has_entity_link = True
                    break

        if "strip_all_if_links" in rules:
            if has_entity_link or LINK_REGEX.search(text) or MD_LINK_REGEX.search(text):
                text = ""

        if text and "block_keywords" in rules:
            for kw, is_regex in get_keywords(chat_id):
                if is_regex:
                    try:
                        if re.search(kw, text, re.IGNORECASE): text = ""; break
                    except re.error:
                        continue
                else:
                    if kw.lower() in text.lower(): text = ""; break

        if text and "clean_links" in rules:
            text = LINK_REGEX.sub("", text)
            text = MD_LINK_REGEX.sub("", text)

        if text and "remove_at_prefix" in rules:
            text = AT_PREFIX_REGEX.sub("", text)

        if text:
            maxlen = _parse_maxlen(rules)
            if maxlen and len(text) > maxlen: text = ""

        if text:
            text = "\n".join(line.strip() for line in text.splitlines())
            text = re.sub(r"\s{2,}", " ", text).strip()

    footer = get_footer(chat_id)
    if footer:
        text = f"{text}\n\n{footer}" if text else footer

    return text or None