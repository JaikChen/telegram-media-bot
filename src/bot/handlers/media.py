import asyncio
import logging
from cachetools import TTLCache
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.data.repositories import ChatRepository
from src.bot.domain.media_service import MediaService
from src.bot.domain.forwarding import ForwardingService
from src.bot.handlers.extras import is_flooding
from src.bot.utils.helpers import is_admin

logger = logging.getLogger(__name__)

# Album aggregation & locking structures
album_cache = TTLCache(maxsize=5000, ttl=600)
processed_gids = TTLCache(maxsize=10000, ttl=300)
debounce_tasks = {}
album_locks = {}


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unified handler for all media types with self-cleaning support."""
    msg = update.effective_message
    if not msg:
        return

    cid = str(msg.chat_id)
    # Ensure chat is known
    await ChatRepository.save_chat(cid, msg.chat.title or "Unknown")

    # 1. Permission & Locking Checks
    if await ChatRepository.is_locked(cid):
        return

    # Flood protection for non-admins
    if not await is_admin(update):
        if await is_flooding(msg.from_user.id if msg.from_user else 0):
            return

    allowed = await ChatRepository.get_media_filter(cid)
    _, _, mt = MediaService._get_media_info(msg)
    if allowed and mt and mt not in allowed:
        return

    # 2. Handle Albums (Media Groups)
    if msg.media_group_id:
        gid = msg.media_group_id
        if gid in processed_gids:
            return

        if gid not in album_cache:
            album_cache[gid] = {"messages": {}, "last_arrival": 0}

        album_cache[gid]["messages"][msg.message_id] = msg
        album_cache[gid]["last_arrival"] = asyncio.get_event_loop().time()

        if gid not in debounce_tasks:
            debounce_tasks[gid] = asyncio.create_task(process_album_debounce(context, gid, cid, msg.message_id))
        return

    # 3. Handle Single Media
    should_delete = await MediaService.process_incoming_message(msg, context.bot.id)

    if should_delete:
        try:
            await msg.delete()
        except Exception as e:
            logger.warning(f"⚠️ Could not delete source message: {e}")

    await ForwardingService.trigger_worker(context)


async def process_album_debounce(context: ContextTypes.DEFAULT_TYPE, gid: str, cid: str, smid: int):
    """Wait for all items in an album to arrive before processing atomically."""
    if gid not in album_locks:
        album_locks[gid] = asyncio.Lock()

    async with album_locks[gid]:
        if gid in processed_gids:
            debounce_tasks.pop(gid, None)
            return

        start_time = asyncio.get_event_loop().time()
        while True:
            await asyncio.sleep(0.5)
            data = album_cache.get(gid)
            if not data:
                break

            now = asyncio.get_event_loop().time()
            # 2.0s of silence after last message or 12s maximum total wait
            if now - data["last_arrival"] >= 2.0 or now - start_time > 12.0:
                break

        data = album_cache.pop(gid, None)
        if not data or not data["messages"]:
            debounce_tasks.pop(gid, None)
            album_locks.pop(gid, None)
            return

        processed_gids[gid] = True
        msgs = sorted(list(data["messages"].values()), key=lambda x: x.message_id)
        should_delete = False
        try:
            should_delete = await MediaService.process_album(msgs, gid, cid, smid, context.bot.id)
        except Exception as e:
            logger.error(f"❌ Error in process_album for group {gid}: {e}")
        finally:
            debounce_tasks.pop(gid, None)
            album_locks.pop(gid, None)

            if should_delete:
                try:
                    for m in msgs:
                        await m.delete()
                except Exception as e:
                    logger.warning(f"⚠️ Could not delete source album in group: {e}")

            await ForwardingService.trigger_worker(context)
