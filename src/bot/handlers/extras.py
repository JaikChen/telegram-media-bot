# handlers/extras.py
"""
Extra features including edit synchronization, weekly reports, and anti-flood protection.
"""

import asyncio
import logging
from typing import Dict, List
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.data.repositories import MediaRepository
from src.cleaner.engine import clean_caption, restore_all_tags
from src.bot.utils.helpers import escape_markdown

logger = logging.getLogger(__name__)

# --- User Anti-Flood (简单防刷屏) ---
user_flood_cache: Dict[int, List[float]] = {}


async def is_flooding(user_id: int, limit: int = 100) -> bool:
    """
    Check if a user is sending too many messages within a short time.

    Args:
        user_id: The Telegram user ID.
        limit: Max number of messages allowed per 60 seconds.
    """
    now = asyncio.get_event_loop().time()
    times = user_flood_cache.get(user_id, [])
    # 仅保留最近 60 秒的时间戳
    times = [t for t in times if now - t < 60]
    times.append(now)
    user_flood_cache[user_id] = times
    return len(times) > limit


# --- Edit Sync (编辑同步) ---


async def handle_edit_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Synchronize edits made to a message's caption to its forwarded versions.

    When a message in a source group is edited, this handler finds all target
    channels it was forwarded to and updates their captions accordingly.
    """
    msg = update.edited_message or update.edited_channel_post
    if not msg:
        return

    cid, mid = str(msg.chat_id), str(msg.message_id)
    try:
        # 获取此消息的所有转发目标
        targets = await MediaRepository.get_forwarded_targets(cid, mid)
        if not targets:
            return

        new_cap = msg.caption or ""
        entities = msg.caption_entities

        for t_cid, t_mid in targets:
            # 对每个目标重新执行一次清理逻辑 (因为不同频道可能有不同规则/页脚)
            cleaned = restore_all_tags(new_cap, await clean_caption(new_cap, t_cid, entities=entities))
            try:
                await context.bot.edit_message_caption(
                    chat_id=t_cid, message_id=int(t_mid), caption=escape_markdown(cleaned), parse_mode="Markdown"
                )
                logger.info(f"Edit Sync: Updated msg {t_mid} in chat {t_cid}")
            except Exception as e:
                logger.warning(f"⚠️ Edit Sync failed for {t_cid} message {t_mid}: {e}")
    except Exception as e:
        logger.error(f"Error in handle_edit_caption: {e}")


# --- Local Analytics Report (活跃度周报) ---


async def send_weekly_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Job callback to send a weekly activity report to the log channel.
    Generates statistics on the most active chats.
    """
    try:
        stats = await MediaRepository.get_stats()
        if not stats:
            return

        report = "📊 **Bot 运营统计看板 (本周)**\n\n"
        total = 0
        top_chats = []

        for cid, count in stats[:5]:
            total += count
            try:
                chat = await context.bot.get_chat(cid)
                title = chat.title or "Unknown"
            except Exception:
                title = str(cid)
            top_chats.append(f"• `{title}`: {count} 条")

        report += f"✅ 总处理媒体: {total} 次\n"
        report += "\n**🔥 活跃榜单:**\n" + "\n".join(top_chats)
        report += "\n\n_注: 统计数据基于本地 SQLite 聚合查询。_"

        # 发送到日志频道
        log_cid = await MediaRepository.get_log_channel_global()
        if log_cid:
            await context.bot.send_message(chat_id=log_cid, text=report, parse_mode="Markdown")
            logger.info("Weekly report sent to log channel.")
    except Exception as e:
        logger.error(f"Error in send_weekly_report: {e}")
