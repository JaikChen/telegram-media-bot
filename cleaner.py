import re
from telegram import MessageEntity
from db import get_keywords, get_rules, get_replacements, get_footer, is_user_whitelisted
from config import WHITELIST

# 预编译正则，提高性能
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

    # 仅补回缺失的标签
    missing = [tag for tag in found_tags if tag not in existing]
    if missing:
        result = (result + " " + " ".join(missing)).strip()

    return result or None


def clean_caption(text: str | None, chat_id: str, user_id: int | None = None, entities: list = None) -> str | None:
    text = text or ""

    # 白名单检查
    if chat_id in WHITELIST: return text
    if user_id and is_user_whitelisted(chat_id, str(user_id)): return text

    rules = get_rules(chat_id)
    replacements = get_replacements(chat_id)

    # 替换
    for old, new in replacements:
        text = text.replace(old, new)

    if "keep_all" in rules:
        pass
    else:
        # 链接检测
        has_entity_link = any(ent.type in [MessageEntity.TEXT_LINK, MessageEntity.URL] for ent in (entities or []))

        # 严格删链 (含链接删整条)
        if "strip_all_if_links" in rules:
            if has_entity_link or LINK_REGEX.search(text) or MD_LINK_REGEX.search(text):
                text = ""

        # 温和屏蔽 (删行)
        if text and "clean_keywords" in rules:
            lines = []
            keywords = get_keywords(chat_id)
            for line in text.splitlines():
                if not any((re.search(kw, line, re.IGNORECASE) if is_regex else kw.lower() in line.lower()) for
                           kw, is_regex in keywords):
                    lines.append(line)
            text = "\n".join(lines)

        # 严格屏蔽 (删整条)
        if text and "block_keywords" in rules:
            keywords = get_keywords(chat_id)
            if any((re.search(kw, text, re.IGNORECASE) if is_regex else kw.lower() in text.lower()) for kw, is_regex in
                   keywords):
                text = ""

        # 温和删链 (只删链接文本)
        if text and "clean_links" in rules:
            text = TG_MD_LINK_REGEX.sub("", text)  # 删 Telegram 隐藏链接
            text = MD_LINK_REGEX.sub(r"\1", text)  # MD链接保留标题
            text = LINK_REGEX.sub("", text)  # 删纯文本链接

        # 删 @
        if text and "remove_at_prefix" in rules:
            text = AT_PREFIX_REGEX.sub("", text)

        # 长度限制
        if text:
            for r in rules:
                if r.startswith("maxlen:"):
                    try:
                        maxlen = int(r.split(":")[1])
                        if len(text) > maxlen: text = ""
                    except:
                        pass
                    break

        # 格式化
        if text:
            text = re.sub(r"\n{3,}", "\n\n", text).strip()  # 去除过多空行

    # 页脚
    footer = get_footer(chat_id)
    if footer:
        text = f"{text}\n\n{footer}" if text else footer

    return text or None