import asyncio
import random
import time
import logging
from typing import List, Any
# 修复: 引入了 InputMediaDocument 和 InputMediaAudio，补齐遗漏的合并转发类型支持
from telegram import Bot, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from telegram.error import RetryAfter
from telegram.ext import ContextTypes

from src.bot.data.repositories import MediaRepository, VoteRepository
from src.bot.utils.helpers import log_event, escape_markdown, get_vote_markup

logger = logging.getLogger(__name__)


class ForwardingService:
    _worker_lock = asyncio.Lock()
    _last_send_per_chat: dict[str, float] = {}
    _worker_event = asyncio.Event()
    _is_running = False

    @classmethod
    async def _wait_per_chat_pacing(cls, target_chat_id: str, min_interval: float = 2.0):
        """Enforces a per-chat minimum interval (default 2s) to comply with Telegram API rates (~30 msg/min per chat)."""
        now = time.time()
        last_time = cls._last_send_per_chat.get(str(target_chat_id), 0.0)
        elapsed = now - last_time
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        cls._last_send_per_chat[str(target_chat_id)] = time.time()

    @classmethod
    async def trigger_worker(cls, context: ContextTypes.DEFAULT_TYPE):
        if await MediaRepository.is_forward_paused():
            return
        cls._worker_event.set()
        if not context.job_queue.get_jobs_by_name("forward_worker"):
            min_s, max_s = await MediaRepository.get_delay_settings()
            delay = random.randint(min_s, max_s) if max_s > 0 else 1
            context.job_queue.run_once(cls.forward_worker, delay, name="forward_worker")

    @classmethod
    async def forward_worker(cls, context: ContextTypes.DEFAULT_TYPE):
        if await MediaRepository.is_forward_paused():
            return
        if cls._worker_lock.locked():
            cls._worker_event.set()
            return

        async with cls._worker_lock:
            cls._worker_event.clear()
            while not await MediaRepository.is_forward_paused():
                batch = await MediaRepository.fetch_queue_batch(limit=50)
                if not batch:
                    break

                handled_ids = set()
                try:
                    for row in batch:
                        rid, tcid, mt, fid, cap, sp, fuid, mgid, _, retries, prio, scid, smid, _, _ = row
                        if rid in handled_ids:
                            continue

                        try:
                            await cls._wait_per_chat_pacing(tcid, min_interval=2.0)
                            if mgid:
                                group_rows = await MediaRepository.get_forward_group(tcid, mgid)
                                if not group_rows:
                                    handled_ids.add(rid)
                                    continue
                                success = await cls._process_album_forward(
                                    context.bot, tcid, mgid, group_rows, prio, scid, smid
                                )
                                for gr in group_rows:
                                    handled_ids.add(gr[0])
                            else:
                                success = await cls._process_single_forward(
                                    context.bot, rid, tcid, mt, fid, cap, sp, fuid, prio, scid, smid
                                )
                                handled_ids.add(rid)

                        except RetryAfter as e:
                            logger.warning(f"⚠️ Rate limited for chat {tcid}. Waiting {e.retry_after}s")
                            cls._last_send_per_chat[str(tcid)] = time.time() + e.retry_after
                            await asyncio.sleep(e.retry_after + 1.0)
                            break
                        except Exception as e:
                            logger.error(f"❌ Unexpected error in worker loop for item {rid}: {e}")
                            handled_ids.add(rid)
                            continue
                finally:
                    unhandled = [r[0] for r in batch if r[0] not in handled_ids]
                    if unhandled:
                        await MediaRepository.reset_processing_status(unhandled)

            next_item_time = await MediaRepository.peek_queue()
            if next_item_time is not None:
                min_s, max_s = await MediaRepository.get_delay_settings()
                base_delay = random.randint(min_s, max_s) if max_s > 0 else 1

                if next_item_time > 0:
                    real_now = int(time.time())
                    wait_time = next_item_time - real_now
                    delay = max(1.0, wait_time)
                else:
                    delay = 1.0

                if not context.job_queue.get_jobs_by_name("forward_worker"):
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
                # 1. Delete from queue immediately
                await MediaRepository.delete_queue_items([rid])
                # 2. Record outbound message to block echo detection
                await MediaRepository.record_outbound_message(tcid, str(sent.message_id))
                try:
                    await MediaRepository.log_forward(scid, smid, tcid, str(sent.message_id))
                    if prio < 10:
                        await MediaRepository.add_forward_seen_atomic(tcid, fuid)
                        await log_event(bot, f"📤 <b>单媒体转发成功</b>\n目标: <code>{tcid}</code>", category="forward")
                except Exception as log_err:
                    logger.warning(f"⚠️ Secondary logging/seen operation failed for item {rid}: {log_err}")
                return True
        except RetryAfter:
            raise
        except Exception as e:
            await MediaRepository.increment_retry(rid, reason=str(e))
        return False

    @classmethod
    async def _process_album_forward(
            cls, bot: Bot, tcid: str, mgid: str, group_rows: List[tuple], prio: int, scid: str, smid: str
    ) -> bool:
        from telegram.error import BadRequest
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
                elif m_type == "document":
                    m_cls = InputMediaDocument
                elif m_type == "audio":
                    m_cls = InputMediaAudio
                else:
                    continue
                media.append(m_cls(**params))

            if not media:
                await MediaRepository.delete_forward_group(tcid, mgid)
                return True

            try:
                sent_msgs = await bot.send_media_group(chat_id=tcid, media=media)
            except BadRequest as e:
                if "parse" in str(e).lower() or "entities" in str(e).lower():
                    logger.warning(f"⚠️ Album markdown parse failed for chat {tcid}: {e}. Retrying with plain text...")
                    for i, r in enumerate(group_rows):
                        f_cap = r[4]
                        if i == 0 and f_cap:
                            media[i].caption = f_cap
                            media[i].parse_mode = None
                    sent_msgs = await bot.send_media_group(chat_id=tcid, media=media)
                else:
                    raise

            if sent_msgs:
                # 1. Delete album from queue immediately
                await MediaRepository.delete_forward_group(tcid, mgid)
                # 2. Record all outbound messages to block echo detection
                for sm in sent_msgs:
                    await MediaRepository.record_outbound_message(tcid, str(sm.message_id))
                try:
                    await MediaRepository.log_forward(scid, smid, tcid, str(sent_msgs[0].message_id))
                    if prio < 10:
                        for r in group_rows:
                            await MediaRepository.add_forward_seen_atomic(tcid, r[6])
                        await log_event(bot, f"📤 <b>相册转发成功</b>\n目标: <code>{tcid}</code>", category="forward")
                except Exception as log_err:
                    logger.warning(f"⚠️ Secondary logging/seen operation failed for album {mgid}: {log_err}")
                return True
        except RetryAfter:
            raise
        except Exception as e:
            await MediaRepository.increment_retry_group(tcid, mgid, reason=str(e))
        return False

    @staticmethod
    async def send_single_media(
            bot: Bot, cid: str | int, mt: str, fid: str, cap: str | None = None, markup: Any = None, sp: bool = False
    ):
        from telegram.error import BadRequest

        params = {
            "chat_id": cid,
            "reply_markup": markup,
        }

        if mt not in ["sticker", "video_note"]:
            params["caption"] = escape_markdown(cap) if cap else None
            params["parse_mode"] = "Markdown"

        if mt in ["photo", "video", "animation"]:
            params["has_spoiler"] = sp

        async def _dispatch(p):
            if mt == "photo":
                return await bot.send_photo(photo=fid, **p)
            if mt == "video":
                return await bot.send_video(video=fid, **p)
            if mt == "animation":
                return await bot.send_animation(animation=fid, **p)
            if mt == "document":
                return await bot.send_document(document=fid, **p)
            if mt == "audio":
                return await bot.send_audio(audio=fid, **p)
            if mt == "voice":
                return await bot.send_voice(voice=fid, **p)
            if mt == "video_note":
                return await bot.send_video_note(video_note=fid, **p)
            if mt == "sticker":
                return await bot.send_sticker(sticker=fid, **p)
            return None

        try:
            return await _dispatch(params)
        except BadRequest as e:
            if "parse" in str(e).lower() or "entities" in str(e).lower():
                logger.warning(f"⚠️ Single media markdown parse failed for chat {cid}: {e}. Retrying with plain text...")
                params["caption"] = cap
                params.pop("parse_mode", None)
                return await _dispatch(params)
            raise