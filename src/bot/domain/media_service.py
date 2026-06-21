import logging
from typing import List, Tuple, Optional
from telegram import Message
from src.bot.data.repositories import MediaRepository, ChatRepository
from src.cleaner.engine import clean_caption, restore_all_tags, check_spoiler_tags

logger = logging.getLogger(__name__)


class MediaService:
    """Core business logic for processing, cleaning, and distributing media."""

    @staticmethod
    async def process_incoming_message(msg: Message, bot_id: int) -> bool:
        """
        Determines if a message is a duplicate or needs cleaning/forwarding.
        Returns True if the original message should be deleted.
        """
        cid = str(msg.chat_id)
        fid, fuid, mt = MediaService._get_media_info(msg)
        if not fid:
            return False

        is_from_bot = (msg.from_user and msg.from_user.id == bot_id)

        # 1. Global Deduplication Check
        in_seen, in_forward = await MediaRepository.check_duplicate_status(cid, fuid)

        if in_seen:
            if is_from_bot:
                return False  # Bot's own fully processed message, leave it alone
            else:
                logger.info(f"♻️ [Duplicate] Removing existing media {fuid} in chat {cid}")
                return True  # User duplicate, delete

        if in_forward and not is_from_bot:
            logger.info(f"♻️ [Duplicate] User attempting to post forwarded media {fuid} in chat {cid}")
            return True

        # Mark as seen
        if not await MediaRepository.add_seen_atomic(cid, fuid):
            return True if not is_from_bot else False

        # 2. Preparation for Cleaning
        cap = msg.caption or ""
        sp = await check_spoiler_tags(cap)
        uid = msg.from_user.id if msg.from_user else 0
        chat_title = msg.chat.title or "Unknown"

        # 4. Self-Cleaning (Send purified version back to source)
        if not is_from_bot:
            cleaned_local = restore_all_tags(
                cap, await clean_caption(cap, cid, uid, msg.caption_entities, sp, chat_title=chat_title)
            )
            local_item = {
                "tid": cid,
                "mt": mt,
                "fid": fid,
                "cap": cleaned_local,
                "sp": sp,
                "fuid": fuid,
                "prio": 10,
                "scid": cid,
                "smid": str(msg.message_id),
            }
            await MediaRepository.enqueue_batch([local_item])

        # 5. External Forwarding (采用基于全链路解析的新 API)
        targets = sorted(list(set(await ChatRepository.get_all_cascade_targets(cid))))
        for i, tcid in enumerate(targets):
            if tcid == cid:
                continue

            t_cap = restore_all_tags(cap, await clean_caption(cap, tcid, has_spoiler=sp, chat_title=chat_title))
            item = {
                "tid": tcid,
                "mt": mt,
                "fid": fid,
                "cap": t_cap,
                "sp": sp,
                "fuid": fuid,
                "prio": 5,
                "scid": cid,
                "smid": str(msg.message_id),
            }
            # Stagger each destination channel by 30 seconds
            delay_offset = 30 * i
            await MediaRepository.add_forward_seen_and_enqueue(tcid, item, delay_offset=delay_offset)

        return True if not is_from_bot else False

    @staticmethod
    async def process_album(msgs: List[Message], gid: str, cid: str, smid: int, bot_id: int) -> bool:
        """Processes a media group atomically with self-cleaning and cascading support."""
        if not msgs:
            return False

        cap_msg = next((m for m in msgs if m.caption), msgs[0])
        cap = cap_msg.caption or ""
        entities = cap_msg.caption_entities or []
        sp = await check_spoiler_tags(cap)
        uid = msgs[0].from_user.id if msgs[0].from_user else 0
        chat_title = msgs[0].chat.title or "Unknown"

        is_from_bot = (msgs[0].from_user and msgs[0].from_user.id == bot_id)

        # 1. 修复: 对相册内所有元素进行鉴重，彻底封堵部分重复元素绕过机制
        is_dupe_user = False
        is_dupe_bot = False

        for m in msgs:
            _, fuid, _ = MediaService._get_media_info(m)
            if fuid:
                in_s, in_f = await MediaRepository.check_duplicate_status(cid, fuid)
                if in_s:
                    if is_from_bot:
                        is_dupe_bot = True
                    else:
                        is_dupe_user = True
                elif in_f and not is_from_bot:
                    is_dupe_user = True

        if is_dupe_user:
            logger.info(f"♻️ [Duplicate Album] Removing existing album {gid} in chat {cid}")
            return True
        if is_dupe_bot:
            return False

        # Mark all as processing for Source
        for m in msgs:
            _, fuid, _ = MediaService._get_media_info(m)
            if fuid:
                await MediaRepository.add_seen_atomic(cid, fuid)

        # Self-Cleaning only if NOT from bot
        if not is_from_bot:
            cleaned_local = restore_all_tags(cap, await clean_caption(cap, cid, uid, entities, sp, chat_title=chat_title))
            local_items = []
            for m in msgs:
                fid, fuid, mt = MediaService._get_media_info(m)
                if fid:
                    local_items.append(
                        {
                            "tid": cid,
                            "mt": mt,
                            "fid": fid,
                            "cap": cleaned_local if m == cap_msg else None,
                            "sp": sp,
                            "fuid": fuid,
                            "mgid": gid,
                            "prio": 10,
                            "scid": cid,
                            "smid": str(smid),
                        }
                    )
            await MediaRepository.enqueue_batch(local_items)

        # 2. Forwarding to Targets (采用基于全链路解析的新 API)
        targets = sorted(list(set(await ChatRepository.get_all_cascade_targets(cid))))
        for i, tcid in enumerate(targets):
            if tcid == cid:
                continue
            t_cap = restore_all_tags(cap, await clean_caption(cap, tcid, has_spoiler=sp, chat_title=chat_title))
            forward_items = []
            for m in msgs:
                fid, fuid, mt = MediaService._get_media_info(m)
                if fid:
                    forward_items.append(
                        {
                            "tid": tcid,
                            "mt": mt,
                            "fid": fid,
                            "cap": t_cap if m == cap_msg else None,
                            "sp": sp,
                            "fuid": fuid,
                            "mgid": gid,
                            "prio": 5,
                            "scid": cid,
                            "smid": str(smid),
                        }
                    )
            # Stagger each destination channel by 30 seconds
            delay_offset = 30 * i
            await MediaRepository.add_forward_seen_and_enqueue_album(tcid, forward_items, delay_offset=delay_offset)

        return True if not is_from_bot else False

    @staticmethod
    def _get_media_info(msg: Message) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        if msg.photo:
            return msg.photo[-1].file_id, msg.photo[-1].file_unique_id, "photo"
        if msg.video:
            return msg.video.file_id, msg.video.file_unique_id, "video"
        if msg.animation:
            return msg.animation.file_id, msg.animation.file_unique_id, "animation"
        if msg.document:
            return msg.document.file_id, msg.document.file_unique_id, "document"
        if msg.audio:
            return msg.audio.file_id, msg.audio.file_unique_id, "audio"
        if msg.voice:
            return msg.voice.file_id, msg.voice.file_unique_id, "voice"
        if msg.video_note:
            return msg.video_note.file_id, msg.video_note.file_unique_id, "video_note"
        if msg.sticker:
            return msg.sticker.file_id, msg.sticker.file_unique_id, "sticker"
        return None, None, None