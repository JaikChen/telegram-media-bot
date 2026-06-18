import asyncio
import random
import logging
from typing import List, Any
from telegram import Bot, InputMediaPhoto, InputMediaVideo
from telegram.error import RetryAfter
from telegram.ext import ContextTypes

from src.bot.data.repositories import MediaRepository, VoteRepository
from src.bot.utils.helpers import log_event, escape_markdown, get_vote_markup
# Note: is_voting_enabled will be moved to a service or repository
# For now, we assume it's available in repositories or a common service.

logger = logging.getLogger(__name__)


class ForwardingService:
    _worker_lock = asyncio.Lock()

    @classmethod
    async def trigger_worker(cls, context: ContextTypes.DEFAULT_TYPE):
        if await MediaRepository.is_forward_paused():
            return
        if not context.job_queue.get_jobs_by_name("forward_worker"):
            min_s, max_s = await MediaRepository.get_delay_settings()
            delay = random.randint(min_s, max_s) if max_s > 0 else 1
            context.job_queue.run_once(cls.forward_worker, delay, name="forward_worker")

    @classmethod
    async def forward_worker(cls, context: ContextTypes.DEFAULT_TYPE):
        if await MediaRepository.is_forward_paused():
            return
        if cls._worker_lock.locked():
            return

        async with cls._worker_lock:
            batch = await MediaRepository.fetch_queue_batch(limit=50)
            if not batch:
                return

            handled_ids = set()
            try:
                for row in batch:
                    rid, tcid, mt, fid, cap, sp, fuid, mgid, _, retries, prio, scid, smid, _, _ = row
                    if rid in handled_ids:
                        continue

                    try:
                        if mgid:
                            group_rows = await MediaRepository.get_forward_group(tcid, mgid)
                            if not group_rows:
                                handled_ids.add(rid)
                                continue
                            success = await cls._process_album_forward(
                                context.bot, tcid, mgid, group_rows, prio, scid, smid
                            )
                            if success:
                                for gr in group_rows:
                                    handled_ids.add(gr[0])
                            else:
                                # Mark as handled to avoid immediate retry in this loop if multiple items from same group
                                for gr in group_rows:
                                    handled_ids.add(gr[0])
                        else:
                            success = await cls._process_single_forward(
                                context.bot, rid, tcid, mt, fid, cap, sp, fuid, prio, scid, smid
                            )
                            if success:
                                handled_ids.add(rid)
                        
                        await asyncio.sleep(0.2) # Small delay between messages
                    except RetryAfter as e:
                        logger.warning(f"⚠️ Rate limited. Waiting {e.retry_after}s")
                        await asyncio.sleep(e.retry_after)
                        break # Stop this worker batch on rate limit
                    except Exception as e:
                        logger.error(f"❌ Unexpected error in worker loop for item {rid}: {e}")
                        handled_ids.add(rid) # Mark as handled to move past it in this batch
                        continue
            finally:
                unhandled = [r[0] for r in batch if r[0] not in handled_ids]
                if unhandled:
                    await MediaRepository.reset_processing_status(unhandled)

            if await MediaRepository.peek_queue():
                min_s, max_s = await MediaRepository.get_delay_settings()
                delay = random.randint(min_s, max_s) if max_s > 0 else 1
                context.job_queue.run_once(cls.forward_worker, delay, name="forward_worker")

    @classmethod
    async def _process_single_forward(
        cls,
        bot: Bot,
        rid: int,
        tcid: str,
        mt: str,
        fid: str,
        cap: str,
        sp: int,
        fuid: str,
        prio: int,
        scid: str,
        smid: str,
    ) -> bool:
        try:
            markup = get_vote_markup(0, 0) if await VoteRepository.is_voting_enabled(tcid) else None
            sent = await cls.send_single_media(bot, tcid, mt, fid, cap, markup, bool(sp))
            if sent:
                await MediaRepository.log_forward(scid, smid, tcid, str(sent.message_id))
                if prio < 10:
                    await MediaRepository.add_forward_seen_atomic(tcid, fuid)
                    await log_event(bot, f"📤 <b>单媒体转发成功</b>\n目标: <code>{tcid}</code>", category="forward")
                await MediaRepository.delete_queue_items([rid])
                return True
        except RetryAfter:
            raise  # Let RetryAfter bubble up to the main loop to pause the worker correctly
        except Exception as e:
            await MediaRepository.increment_retry(rid, reason=str(e))
        return False

    @classmethod
    async def _process_album_forward(
        cls, bot: Bot, tcid: str, mgid: str, group_rows: List[tuple], prio: int, scid: str, smid: str
    ) -> bool:
        try:
            media = []
            for i, r in enumerate(group_rows):
                m_type, f_id, f_cap, f_sp = r[2], r[3], r[4], bool(r[5])
                params = {
                    "media": f_id,
                    "caption": escape_markdown(f_cap) if i == 0 and f_cap else None,
                    "parse_mode": "Markdown",
                }
                if m_type == "photo":
                    m_cls = InputMediaPhoto
                    params["has_spoiler"] = f_sp
                elif m_type == "video":
                    m_cls = InputMediaVideo
                    params["has_spoiler"] = f_sp
                else:
                    continue
                media.append(m_cls(**params))

            if not media:
                await MediaRepository.delete_forward_group(tcid, mgid)
                return True

            sent_msgs = await bot.send_media_group(chat_id=tcid, media=media)
            if sent_msgs:
                await MediaRepository.log_forward(scid, smid, tcid, str(sent_msgs[0].message_id))
                await MediaRepository.delete_forward_group(tcid, mgid)
                if prio < 10:
                    await log_event(bot, f"📤 <b>相册转发成功</b>\n目标: <code>{tcid}</code>", category="forward")
                return True
        except RetryAfter:
            raise  # Let RetryAfter bubble up to the main loop to pause the worker correctly
        except Exception as e:
            await MediaRepository.increment_retry_group(tcid, mgid, reason=str(e))
        return False

    @staticmethod
    async def send_single_media(
        bot: Bot, cid: str | int, mt: str, fid: str, cap: str | None = None, markup: Any = None, sp: bool = False
    ):
        params = {
            "chat_id": cid,
            "reply_markup": markup,
        }
        
        # Add captions to text-supporting media
        if mt not in ["sticker", "video_note"]:
            params["caption"] = escape_markdown(cap) if cap else None
            params["parse_mode"] = "Markdown"
            
        # Add spoiler to supported types
        if mt in ["photo", "video", "animation"]:
            params["has_spoiler"] = sp

        if mt == "photo":
            return await bot.send_photo(photo=fid, **params)
        if mt == "video":
            return await bot.send_video(video=fid, **params)
        if mt == "animation":
            return await bot.send_animation(animation=fid, **params)
        if mt == "document":
            return await bot.send_document(document=fid, **params)
        if mt == "audio":
            return await bot.send_audio(audio=fid, **params)
        if mt == "voice":
            return await bot.send_voice(voice=fid, **params)
        if mt == "video_note":
            return await bot.send_video_note(video_note=fid, **params)
        if mt == "sticker":
            return await bot.send_sticker(sticker=fid, **params)
        return None
