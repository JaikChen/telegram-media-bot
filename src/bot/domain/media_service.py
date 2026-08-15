import logging
from typing import List, Tuple, Optional
from telegram import Message
from src.bot.data.repositories import MediaRepository, ChatRepository
from src.cleaner.engine import clean_caption, restore_all_tags, check_spoiler_tags

logger = logging.getLogger(__name__)


def is_forwarded_message(msg: Message) -> bool:
    """Checks if a message is forwarded from another chat/user."""
    if not msg:
        return False
    return bool(
        getattr(msg, "forward_origin", None)
        or getattr(msg, "forward_date", None)
        or getattr(msg, "forward_from", None)
        or getattr(msg, "forward_from_chat", None)
        or getattr(msg, "forward_sender_name", None)
    )


class MediaService:
    """Core business logic for processing, cleaning, and distributing media."""

    @staticmethod
    async def process_incoming_message(msg: Message, bot_id: int) -> bool:
        """
        Processes an incoming single media message.
        Strips forward header and forwards cleaned media to all configured target channels.
        Guarantees zero duplicate sends and zero self-cleaning echo loops.
        """
        cid = str(msg.chat_id)
        smid = str(msg.message_id)
        fid, fuid, mt = MediaService._get_media_info(msg)
        if not fid or not fuid:
            return False

        # 1. Outbound / Self-echo check: Ignore messages sent by the bot
        if msg.from_user and msg.from_user.id == bot_id:
            return False
        if await MediaRepository.is_outbound_message(cid, smid):
            return False

        # 2. Inbound deduplication check
        if await MediaRepository.is_processed_inbound(cid, smid, fuid):
            return False
        if not await MediaRepository.mark_processed_inbound(cid, smid, fuid):
            return False

        # 3. Preparation for Cleaning
        cap = msg.caption or ""
        sp = await check_spoiler_tags(cap)
        uid = msg.from_user.id if msg.from_user else 0
        chat_title = msg.chat.title or "Unknown"

        # Clean caption using source rules first
        cleaned_source = restore_all_tags(
            cap, await clean_caption(cap, cid, uid, msg.caption_entities, sp, chat_title=chat_title)
        )

        is_forwarded = is_forwarded_message(msg)
        is_group = (msg.chat.type in ["group", "supergroup"])
        is_channel = (msg.chat.type == "channel")

        # 4. External Target Forwarding (A -> B, A -> C)
        targets = [t for t in sorted(list(set(await ChatRepository.get_all_cascade_targets(cid)))) if t != cid]
        enqueued_any = False

        if targets:
            for i, tcid in enumerate(targets):
                t_cap = restore_all_tags(
                    cleaned_source, await clean_caption(cleaned_source, tcid, has_spoiler=sp, chat_title=chat_title)
                )
                item = {
                    "tid": tcid,
                    "mt": mt,
                    "fid": fid,
                    "cap": t_cap,
                    "sp": sp,
                    "fuid": fuid,
                    "prio": 5,
                    "scid": cid,
                    "smid": smid,
                }
                delay_offset = 30 * i
                enqueued = await MediaRepository.add_forward_seen_and_enqueue(tcid, item, delay_offset=delay_offset)
                if enqueued:
                    enqueued_any = True

        # 5. In-Place De-Sourcing / Self-Cleaning in Source Chat
        # Trigger in-place clean post if:
        # - Message was manually forwarded into channel/group/private (is_forwarded is True)
        # - OR no external targets exist (e.g. Private DM or in-place cleaning group)
        needs_inplace = is_forwarded or (not targets and not is_channel)

        if needs_inplace:
            item = {
                "tid": cid,
                "mt": mt,
                "fid": fid,
                "cap": cleaned_source,
                "sp": sp,
                "fuid": fuid,
                "prio": 10,
                "scid": cid,
                "smid": smid,
            }
            enqueued = await MediaRepository.add_forward_seen_and_enqueue(cid, item, delay_offset=0)
            if enqueued:
                enqueued_any = True

        # Delete original message if:
        # - It was a forwarded message in any channel or group (strip source in place)
        # - OR it was posted in a group with self-cleaning
        should_delete = (is_forwarded and (is_channel or is_group)) or (is_group and enqueued_any)
        return should_delete

    @staticmethod
    async def process_album(msgs: List[Message], gid: str, cid: str, smid: int, bot_id: int) -> bool:
        """Processes a media group (album) atomically without loop feedback."""
        if not msgs:
            return False

        # 1. Outbound / Self-echo check
        if msgs[0].from_user and msgs[0].from_user.id == bot_id:
            return False
        if await MediaRepository.is_outbound_message(cid, str(smid)):
            return False

        # 2. Inbound deduplication for all items in the album
        valid_msgs = []
        for m in msgs:
            m_smid = str(m.message_id)
            _, fuid, _ = MediaService._get_media_info(m)
            if fuid:
                if await MediaRepository.is_processed_inbound(cid, m_smid, fuid):
                    continue
                if await MediaRepository.mark_processed_inbound(cid, m_smid, fuid, gid):
                    valid_msgs.append(m)

        if not valid_msgs:
            return False

        cap_msg = next((m for m in valid_msgs if m.caption), valid_msgs[0])
        cap = cap_msg.caption or ""
        entities = cap_msg.caption_entities or []
        sp = await check_spoiler_tags(cap)
        uid = valid_msgs[0].from_user.id if valid_msgs[0].from_user else 0
        chat_title = valid_msgs[0].chat.title or "Unknown"

        # Clean caption
        cleaned_source = restore_all_tags(
            cap, await clean_caption(cap, cid, uid, entities, sp, chat_title=chat_title)
        )

        is_forwarded = any(is_forwarded_message(m) for m in valid_msgs)
        is_group = (valid_msgs[0].chat.type in ["group", "supergroup"])
        is_channel = (valid_msgs[0].chat.type == "channel")

        # 3. External Target Forwarding
        targets = [t for t in sorted(list(set(await ChatRepository.get_all_cascade_targets(cid)))) if t != cid]
        enqueued_any = False

        if targets:
            for i, tcid in enumerate(targets):
                t_cap = restore_all_tags(
                    cleaned_source, await clean_caption(cleaned_source, tcid, has_spoiler=sp, chat_title=chat_title)
                )
                forward_items = []
                for m in valid_msgs:
                    fid, fuid, mt = MediaService._get_media_info(m)
                    if fid and fuid:
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
                delay_offset = 30 * i
                enqueued = await MediaRepository.add_forward_seen_and_enqueue_album(tcid, forward_items, delay_offset=delay_offset)
                if enqueued:
                    enqueued_any = True

        # 4. In-Place De-Sourcing / Self-Cleaning in Source Chat
        needs_inplace = is_forwarded or (not targets and not is_channel)

        if needs_inplace:
            forward_items = []
            for m in valid_msgs:
                fid, fuid, mt = MediaService._get_media_info(m)
                if fid and fuid:
                    forward_items.append(
                        {
                            "tid": cid,
                            "mt": mt,
                            "fid": fid,
                            "cap": cleaned_source if m == cap_msg else None,
                            "sp": sp,
                            "fuid": fuid,
                            "mgid": gid,
                            "prio": 10,
                            "scid": cid,
                            "smid": str(smid),
                        }
                    )
            enqueued = await MediaRepository.add_forward_seen_and_enqueue_album(cid, forward_items, delay_offset=0)
            if enqueued:
                enqueued_any = True

        should_delete = (is_forwarded and (is_channel or is_group)) or (is_group and enqueued_any)
        return should_delete

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