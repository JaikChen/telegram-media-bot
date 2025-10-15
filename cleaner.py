# cleaner.py
# 用于清理说明文字中的链接、@前缀、关键词等内容，支持组合规则

import re
from db import get_keywords, get_rules
from config import WHITELIST

# 正则表达式定义
LINK_REGEX = re.compile(r"(https?://\S+|www\.\S+|t\.me/\S+)", re.IGNORECASE)
MD_LINK_REGEX = re.compile(r"\[[^\]]+\]\(https?://[^)]+\)", re.IGNORECASE)
AT_PREFIX_REGEX = re.compile(r"@\w+")

def _parse_maxlen(rules: list[str]) -> int | None:
    """解析 maxlen:NN 规则"""
    for r in rules:
        if r.startswith("maxlen:"):
            try:
                return int(r.split(":", 1)[1])
            except ValueError:
                return None
    return None

def clean_caption(text: str | None, chat_id: str) -> str | None:
    """根据频道规则清理说明文字"""
    if not text:
        return None

    # 白名单：不清理
    if chat_id in WHITELIST:
        return text.strip()

    rules = get_rules(chat_id)

    # 保留所有说明
    if "keep_all" in rules:
        return text.strip()

    # 有链接就整段删除
    if "strip_all_if_links" in rules:
        if LINK_REGEX.search(text) or MD_LINK_REGEX.search(text):
            return None

    # 关键词屏蔽
    if "block_keywords" in rules:
        for kw, is_regex in get_keywords(chat_id):
            if is_regex:
                if re.search(kw, text, re.IGNORECASE):
                    return None
            else:
                if kw.lower() in text.lower():
                    return None

    # 删除链接
    if "clean_links" in rules:
        text = LINK_REGEX.sub("", text)
        text = MD_LINK_REGEX.sub("", text)

    # 删除 @前缀
    if "remove_at_prefix" in rules:
        text = AT_PREFIX_REGEX.sub("", text)

    # 长度限制
    maxlen = _parse_maxlen(rules)
    if maxlen and len(text) > maxlen:
        return None

    # 清理多余空格和换行
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"\s{2,}", " ", text).strip()

    return text or None