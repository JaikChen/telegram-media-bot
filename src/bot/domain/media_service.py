import logging
from typing import List, Tuple, Optional
from telegram import Message
from src.bot.data.repositories import MediaRepository, ChatRepository
from src.cleaner.engine import clean_caption, restore_all_tags, check_spoiler_tags

logger = logging.getLogger(__name__)


class MediaService:
    """Core business logic for processing, cleaning, and distributing media."""

    @staticmethod
    async def process_incoming_message(msg: Message) -> bool:
        """
        Determines if a message is a duplicate or needs cleaning.
        Returns True if the original message should be deleted.
        """
        cid = str(msg.chat_id)
        fid, fuid, mt = MediaService._get_media_info(msg)
        if not fid:
            return False

        # 1. Global Deduplication Check
        if await MediaRepository.is_duplicate_globally(cid, fuid):
            logger.info(f"♻️ [Duplicate] Removing existing media {fuid} in chat {cid}")
            return True  # Duplicate found, trigger deletion

        # 2. Preparation for Cleaning
        cap = msg.caption or ""
        sp = await check_spoiler_tags(cap)
        uid = msg.from_user.id if msg.from_user else 0
        chat_title = msg.chat.title or "Unknown"

        # 3. Mark as Received (Atomic) - Primary race condition protection
        if not await MediaRepository.add_seen_atomic(cid, fuid):
            logger.info(f"♻️ [Duplicate] Already processed media {fuid} in chat {cid}")
            return True  # Already processed, trigger deletion of the duplicate

        # 4. Self-Cleaning (Send purified version back to source)
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

        # 5. External Forwarding
        targets = sorted(list(set(await ChatRepository.get_forward_targets(cid))))
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

        return True  # New media processed, trigger original deletion

    @staticmethod
    async def process_album(msgs: List[Message], gid: str, cid: str, smid: int) -> bool:
        """Processes a media group atomically with self-cleaning."""
        if not msgs:
            return False

        cap_msg = next((m for m in msgs if m.caption), msgs[0])
        cap = cap_msg.caption or ""
        entities = cap_msg.caption_entities or []
        sp = await check_spoiler_tags(cap)
        uid = msgs[0].from_user.id if msgs[0].from_user else 0
        chat_title = msgs[0].chat.title or "Unknown"

        fid_first, fuid_first, _ = MediaService._get_media_info(msgs[0])
        if not fuid_first:
            return False

        # Deduplication check for the whole album
        if await MediaRepository.is_duplicate_globally(cid, fuid_first):
            return True

        # 1. Self-Cleaning for Source
        if not await MediaRepository.add_seen_atomic(cid, fuid_first):
            logger.info(f"♻️ [Duplicate Album] Already processing album {gid} in chat {cid}")
            return True

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

        # 2. Forwarding to Targets
        targets = sorted(list(set(await ChatRepository.get_forward_targets(cid))))
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

        return True

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
