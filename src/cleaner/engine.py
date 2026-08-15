import re
import logging
from typing import List, Optional
from telegram import MessageEntity
from src.bot.data.repositories import ChatRepository

logger = logging.getLogger(__name__)


def strip_hidden_chars(text: str) -> str:
    """Removes zero-width spaces, invisible formatting, and control characters."""
    if not text:
        return ""
    chars = [
        "\u200b", "\u200c", "\u200d", "\ufeff",
        "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
        "\u2060", "\u2061", "\u2062", "\u2063", "\u2064",
        "\u2069", "\u206a", "\u206b", "\u206c", "\u206d",
        "\u206e", "\u206f", "\u3164", "\uffa0", "\u00a0"
    ]
    for char in chars:
        text = text.replace(char, "")
    return text


def apply_pangu_spacing(text: str) -> str:
    """Inserts space between CJK characters and Latin/digits."""
    if not text:
        return ""
    text = re.sub(r"([\u4e00-\u9fff])([a-zA-Z0-9])", r"\1 \2", text)
    text = re.sub(r"([a-zA-Z0-9])([\u4e00-\u9fff])", r"\1 \2", text)
    return text


def restore_all_tags(original: str, cleaned: str, keywords: list = None) -> str:
    """Restores non-ad hashtags from original if missing and cleaned is non-empty."""
    if not cleaned or not cleaned.strip():
        return ""
    tags = re.findall(r"#[\w\u4e00-\u9fff]+", original)
    for tag in tags:
        is_bad = False
        if keywords:
            for word, is_regex in keywords:
                try:
                    if is_regex:
                        if re.search(word, tag, flags=re.IGNORECASE):
                            is_bad = True
                            break
                    else:
                        if word.lower() in tag.lower():
                            is_bad = True
                            break
                except Exception:
                    pass
        if not is_bad and tag not in cleaned:
            cleaned += f" {tag}"
    return cleaned.strip()


BUILTIN_AD_PATTERNS = [
    r"评论区.*?(看|获取|领取|全集|完整|置顶|见|自取|直达|链接|入口|下载|地址|免费|找)",
    r"留言区.*?(看|获取|领取|全集|完整|置顶|见|自取|直达|链接|入口|下载|地址|免费|找)",
    r"讨论(组|区).*?(看|获取|领取|全集|完整|置顶|见|自取|直达|链接|入口|下载|地址|免费|找)",
    r"(看|获取|免费看|在线看|直达|领取|自取)(全集|完整版|正片|后续|高清版|未删减)",
    r"(全集|完整版|后续|未删减|正片|资源).*?(在|见|请看|直达|自取|获取).*?(评论区|留言区|置顶|群|频道|简介|下方)",
    r"(点击|长按|复制).*?(进入|加入|关注|获取|领取|直达|查看|观看|下载|下方)",
    r"(进群|入群|加入群聊|加群|关注频道|订阅频道).*?(看|获取|免费|无码|资源|全集|高清|体验)",
    r"(解压码|提取码|下载码).*?(评论区|置顶|群|频道|下方)",
    r"(私信|私聊|联系客服|咨询客服|商务合作|代理加盟|加微|加Q)",
]


def is_ad_line(
    line: str,
    keywords: list = None,
    check_links: bool = True,
    check_mentions: bool = True,
    check_kws: bool = True,
    check_builtin_ads: bool = True,
) -> bool:
    """Checks if a single line contains any links, @ mentions, lead-in promos, or keywords."""
    if not line or not line.strip():
        return False

    raw_line = line.strip()
    # Normalize leading quote/markdown symbols (e.g. '> 103p4v-评论区看全集')
    cleaned_line = re.sub(r"^[>\s\-\*•·\d\w_]+-", "", raw_line).strip()
    cleaned_line_generic = re.sub(r"^[>\s\-\*•·]+", "", raw_line).strip()

    if check_links:
        if re.search(r"https?://\S+|t\.me/\S+|telegram\.me/\S+|tg://\S+|www\.\S+|\[[^\]]+\]\([^\)]+\)", raw_line, flags=re.IGNORECASE):
            return True

    if check_mentions:
        if re.search(r"@\w+", raw_line):
            return True

    if check_builtin_ads:
        for pat in BUILTIN_AD_PATTERNS:
            if re.search(pat, raw_line, flags=re.IGNORECASE) or re.search(pat, cleaned_line, flags=re.IGNORECASE) or re.search(pat, cleaned_line_generic, flags=re.IGNORECASE):
                return True

    if check_kws and keywords:
        for word, is_regex in keywords:
            try:
                if is_regex:
                    if re.search(word, raw_line, flags=re.IGNORECASE):
                        return True
                else:
                    if word.lower() in raw_line.lower():
                        return True
            except Exception:
                pass

    return False


async def check_spoiler_tags(text: str) -> bool:
    """Checks if any spoiler keywords are present."""
    if not text:
        return False
    return "#spoiler" in text.lower() or "#剧透" in text.lower()


async def clean_caption(
    text: str,
    chat_id: str,
    user_id: int = 0,
    entities: List[MessageEntity] = None,
    has_spoiler: bool = False,
    chat_title: str = "Unknown",
) -> str:
    """The main entry point for caption purification and ad stripping."""
    # 1. Fetch configuration
    rules = await ChatRepository.get_chat_rules(chat_id)
    keywords = await ChatRepository.get_keywords(chat_id)
    replacements = await ChatRepository.get_replacements(chat_id)
    footer = await ChatRepository.get_footer(chat_id)
    template = await ChatRepository.get_caption_template(chat_id)

    # 2. Preparation
    original_text = strip_hidden_chars(text or "")
    cleaned = original_text

    # 3. Short-circuit if keep_all rule is active
    if "keep_all" in rules:
        if footer:
            cleaned = f"{cleaned.strip()}\n\n{footer}"
        return cleaned.strip()

    # 4. Mode: strip_ad_lines / clean_lines / del_ad_lines
    # Directly delete any line containing links, @ symbols, or keywords
    if any(r in rules for r in ["strip_ad_lines", "clean_lines", "del_ad_lines", "clean_ad_lines"]):
        lines = cleaned.split("\n")
        retained_lines = []
        for line in lines:
            if not is_ad_line(line, keywords, check_links=True, check_mentions=True, check_kws=True):
                retained_lines.append(line)
        cleaned = "\n".join(retained_lines)
        for old, new in replacements:
            cleaned = cleaned.replace(old, new)
    else:
        # Standard granular filtering
        # Check for links
        has_link = bool(
            re.search(r"http[s]?://\S+|t\.me/\S+|telegram\.me/\S+|tg://\S+|www\.\S+", cleaned, re.IGNORECASE)
        )
        if not has_link and entities:
            for ent in entities:
                ent_type = getattr(ent, "type", None)
                if ent_type in ["url", "text_link", "mention"]:
                    has_link = True
                    break

        # If strip_all_if_links rule is active and links are present, wipe caption
        if "strip_all_if_links" in rules and has_link:
            return ""

        # Remove links if clean_links rule is active
        if "clean_links" in rules:
            # Strip markdown links [Text](URL) -> Text
            cleaned = re.sub(r"\[([^\]]+)\]\((?:https?://|t\.me/|telegram\.me/|tg://|www\.)[^\)]+\)", r"\1", cleaned, flags=re.IGNORECASE)
            # Strip plain URLs
            cleaned = re.sub(r"https?://\S+", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"t\.me/\S+", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"telegram\.me/\S+", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"tg://\S+", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"www\.\S+", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"@\w+", "", cleaned)

            # If entities are present, strip text associated with text_link entities if any remain
            if entities and original_text:
                for ent in entities:
                    ent_type = getattr(ent, "type", None)
                    if ent_type == "text_link":
                        offset = getattr(ent, "offset", 0)
                        length = getattr(ent, "length", 0)
                        if offset < len(original_text):
                            link_text = original_text[offset : offset + length]
                            if link_text:
                                cleaned = cleaned.replace(link_text, "")

        # Remove @mentions if remove_at_prefix or remove_at is active
        if "remove_at_prefix" in rules or "remove_at" in rules:
            cleaned = re.sub(r"@\w+", "", cleaned)

        # Apply text replacements
        for old, new in replacements:
            cleaned = cleaned.replace(old, new)

        # Keyword Ad Blocking / Cleaning
        if "block_keywords" in rules:
            # 严格屏蔽 (发现关键词删整条)
            for word, is_regex in keywords:
                try:
                    if is_regex:
                        if re.search(word, cleaned, flags=re.IGNORECASE):
                            return ""
                    else:
                        if word.lower() in cleaned.lower():
                            return ""
                except Exception as e:
                    logger.warning(f"Invalid regex/keyword '{word}': {e}")
        elif "clean_keywords" in rules:
            # 温和屏蔽 (仅删含广告关键词的行)
            lines = cleaned.split("\n")
            retained_lines = []
            for line in lines:
                line_has_kw = False
                for word, is_regex in keywords:
                    try:
                        if is_regex:
                            if re.search(word, line, flags=re.IGNORECASE):
                                line_has_kw = True
                                break
                        else:
                            if word.lower() in line.lower():
                                line_has_kw = True
                                break
                    except Exception:
                        pass
                if not line_has_kw:
                    retained_lines.append(line)
            cleaned = "\n".join(retained_lines)
        else:
            # 默认词级过滤
            for word, is_regex in keywords:
                try:
                    if is_regex:
                        cleaned = re.sub(word, "", cleaned, flags=re.IGNORECASE)
                    else:
                        pattern = re.compile(re.escape(word), re.IGNORECASE)
                        cleaned = pattern.sub("", cleaned)
                except Exception as e:
                    logger.warning(f"Invalid regex/keyword '{word}': {e}")

    cleaned = cleaned.strip()
    if not cleaned:
        return ""

    # 5. Apply maxlen truncation if specified (e.g. maxlen:50)
    for rule in rules:
        if rule.startswith("maxlen:"):
            try:
                max_l = int(rule.split(":")[1])
                if len(cleaned) > max_l:
                    cleaned = cleaned[:max_l].strip()
            except ValueError:
                pass

    # 6. Apply pangu formatting spacing if requested
    if "pangu" in rules:
        cleaned = apply_pangu_spacing(cleaned)

    # 7. Apply Template if exists
    if template and cleaned:
        from datetime import datetime

        vars_dict = {
            "{orig}": cleaned,
            "{title}": chat_title,
            "{cid}": chat_id,
            "{date}": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "{user}": str(user_id) if user_id else "Unknown",
        }
        final_text = template
        for k, v in vars_dict.items():
            final_text = final_text.replace(k, v)
        cleaned = final_text

    # 8. Add footer
    if footer and cleaned:
        cleaned = f"{cleaned.strip()}\n\n{footer}"
    elif footer and not cleaned and "keep_all" not in rules:
        cleaned = footer

    return cleaned.strip()


