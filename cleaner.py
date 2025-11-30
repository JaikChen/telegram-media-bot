# cleaner.py
# 文本处理核心模块：包含清理、检测、恢复等所有字符串操作

import re
from telegram import MessageEntity
from db import get_keywords, get_rules, get_replacements, get_footer, is_user_whitelisted
from config import WHITELIST

# =========================
# 正则表达式定义
# =========================
LINK_REGEX = re.compile(r"(https?://[^\s]+|www\.[^\s]+|t\.me/[^\s]+)", re.IGNORECASE)
TG_MD_LINK_REGEX = re.compile(r"\[[^\]]+\]\((?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/[^\s)]+\)", re.IGNORECASE)
MD_LINK_REGEX = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", re.IGNORECASE)
AT_PREFIX_REGEX = re.compile(r"@\S+")
# [新增] 剧透标签正则
SPOILER_REGEX = re.compile(r'(#spoiler|#剧透|#nsfw)', re.IGNORECASE)
# [新增] 通用 Hashtag 正则
HASHTAG_REGEX = re.compile(r'(#[\w\u4e00-\u9fa5]+)', re.IGNORECASE)


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
# [新增] 辅助功能函数 (从 media.py 移入)
# =========================

def check_spoiler_tags(text: str) -> bool:
    """检查是否含有剧透标签 (用于开启遮罩效果)"""
    if not text: return False
    return bool(SPOILER_REGEX.search(text))


def restore_all_tags(original_text: str, cleaned_text: str | None) -> str | None:
    """
    回填所有 Hashtag
    如果原始文本中有 #标签，但清理后的文本丢失了它们，则全部补回。
    """
    if not original_text:
        return cleaned_text

    found_tags = HASHTAG_REGEX.findall(original_text)

    if not found_tags:
        return cleaned_text

    result = cleaned_text or ""

    for tag in found_tags:
        # 如果新文本里没有这个 Tag，补加上去
        if tag not in result:
            if result:
                result += f" {tag}"
            else:
                result = tag

    return result.strip() or None


# =========================
# 主清理函数
# =========================
def clean_caption(text: str | None, chat_id: str, user_id: str | int | None = None,
                  entities: list = None) -> str | None:
    """
    根据频道规则清理说明文字
    """
    text = text or ""

    # 1. 全局白名单
    if chat_id in WHITELIST:
        return text.strip() or None

    # 2. 群组用户白名单
    if user_id and is_user_whitelisted(chat_id, str(user_id)):
        return text.strip() or None

    rules = get_rules(chat_id)
    replacements = get_replacements(chat_id)

    # 3. 关键词替换 (最优先执行)
    if replacements:
        for old, new in replacements:
            text = text.replace(old, new)

    if "keep_all" in rules:
        pass
    else:
        # 检测实体链接
        has_entity_link = False
        if entities:
            for ent in entities:
                if ent.type in [MessageEntity.TEXT_LINK, MessageEntity.URL]:
                    has_entity_link = True
                    break

        # [温和模式] 行清理
        if text and "clean_keywords" in rules:
            lines = text.splitlines()
            cleaned_lines = []
            keywords = get_keywords(chat_id)

            for line in lines:
                is_bad = False
                for kw, is_regex in keywords:
                    if is_regex:
                        try:
                            if re.search(kw, line, re.IGNORECASE):
                                is_bad = True;
                                break
                        except re.error:
                            continue
                    else:
                        if kw.lower() in line.lower():
                            is_bad = True;
                            break
                if not is_bad:
                    cleaned_lines.append(line)
            text = "\n".join(cleaned_lines)

        # [严格删链]
        if "strip_all_if_links" in rules:
            if has_entity_link or LINK_REGEX.search(text) or MD_LINK_REGEX.search(text):
                text = ""

        # [严格屏蔽]
        if text and "block_keywords" in rules:
            for kw, is_regex in get_keywords(chat_id):
                if is_regex:
                    try:
                        if re.search(kw, text, re.IGNORECASE): text = ""; break
                    except re.error:
                        continue
                else:
                    if kw.lower() in text.lower(): text = ""; break

        # [温和删链]
        if text and "clean_links" in rules:
            text = TG_MD_LINK_REGEX.sub("", text)
            text = MD_LINK_REGEX.sub(r"\1", text)
            text = LINK_REGEX.sub("", text)

        # [删除引用]
        if text and "remove_at_prefix" in rules:
            text = AT_PREFIX_REGEX.sub("", text)

        # [长度限制]
        if text:
            maxlen = _parse_maxlen(rules)
            if maxlen and len(text) > maxlen: text = ""

        # 格式整理
        if text:
            text = "\n".join(line.strip() for line in text.splitlines())
            text = re.sub(r"\s{2,}", " ", text).strip()

    # 4. 追加页脚
    footer = get_footer(chat_id)
    if footer:
        text = f"{text}\n\n{footer}" if text else footer

    return text or None