# cleaner.py
# 用于清理说明文字中的链接、@前缀、关键词等内容，支持组合规则

import re
from db import get_keywords, get_rules, get_replacements, get_footer  # [修改] 增加导入
from config import WHITELIST

# =========================
# 正则表达式定义（增强版）
# =========================
# 链接匹配：支持 http/https、www、t.me，允许括号、中文符号
LINK_REGEX = re.compile(r"(https?://[^\s]+|www\.[^\s]+|t\.me/[^\s]+)", re.IGNORECASE)
# Markdown 链接 [文字](url)
MD_LINK_REGEX = re.compile(r"\[[^\]]+\]\((https?://[^\s)]+)\)", re.IGNORECASE)
# @匹配：支持中文昵称里的 @
AT_PREFIX_REGEX = re.compile(r"@\S+")


# =========================
# 工具函数
# =========================
def _parse_maxlen(rules: list[str]) -> int | None:
    """解析 maxlen:NN 规则"""
    for r in rules:
        if r.startswith("maxlen:"):
            try:
                return int(r.split(":", 1)[1])
            except ValueError:
                return None
    return None


# =========================
# 主清理函数
# =========================
def clean_caption(text: str | None, chat_id: str) -> str | None:
    """根据频道规则清理说明文字"""
    text = text or ""  # [修改] 即使为空也初始化为空字符串，以便后续追加页脚

    # 白名单：不清理
    if chat_id in WHITELIST:
        return text.strip() or None

    rules = get_rules(chat_id)

    # [新增] 关键词替换 (优先执行)
    replacements = get_replacements(chat_id)
    if replacements:
        for old, new in replacements:
            text = text.replace(old, new)

    # 保留所有说明（但替换依然生效，页脚依然生效）
    # 注意：如果规则是 keep_all，这里可以选择直接跳过删除逻辑
    if "keep_all" in rules:
        pass  # 继续向下执行以添加页脚，或在这里直接返回
    else:
        # 有链接就整段删除
        if "strip_all_if_links" in rules:
            if LINK_REGEX.search(text) or MD_LINK_REGEX.search(text):
                text = ""  # 变为空字符串

        # 关键词屏蔽 (如果变为空了就没必要查了)
        if text and "block_keywords" in rules:
            for kw, is_regex in get_keywords(chat_id):
                if is_regex:
                    try:
                        if re.search(kw, text, re.IGNORECASE):
                            text = ""
                            break
                    except re.error:
                        continue
                else:
                    if kw.lower() in text.lower():
                        text = ""
                        break

        # 删除链接
        if text and "clean_links" in rules:
            text = LINK_REGEX.sub("", text)
            text = MD_LINK_REGEX.sub("", text)

        # 删除 @前缀
        if text and "remove_at_prefix" in rules:
            text = AT_PREFIX_REGEX.sub("", text)

        # 长度限制
        if text:
            maxlen = _parse_maxlen(rules)
            if maxlen and len(text) > maxlen:
                text = ""

        # 清理多余空格和换行
        if text:
            text = "\n".join(line.strip() for line in text.splitlines())
            text = re.sub(r"\s{2,}", " ", text).strip()

    # [新增] 追加自定义页脚
    footer = get_footer(chat_id)
    if footer:
        if text:
            text = f"{text}\n\n{footer}"
        else:
            text = footer

    return text or None