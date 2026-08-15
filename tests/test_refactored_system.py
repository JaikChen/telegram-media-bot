import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Message, Chat, User, PhotoSize, Video
from src.bot.domain.media_service import MediaService
from src.bot.data.repositories import MediaRepository, ChatRepository
from src.cleaner.engine import clean_caption


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.id = 123456789
    return bot


def create_mock_message(msg_id: int, chat_id: int, chat_type: str = "channel", text: str = "", fuid: str = "fuid_test_1"):
    msg = MagicMock(spec=Message)
    msg.message_id = msg_id
    msg.chat = MagicMock(spec=Chat)
    msg.chat.id = chat_id
    msg.chat.type = chat_type
    msg.chat.title = "Test Channel"
    msg.chat_id = chat_id
    msg.caption = text
    msg.caption_entities = []
    msg.from_user = None if chat_type == "channel" else MagicMock(spec=User, id=999)
    msg.media_group_id = None

    # Video mock
    vid = MagicMock(spec=Video)
    vid.file_id = f"fid_{fuid}"
    vid.file_unique_id = fuid
    msg.video = vid
    msg.photo = None
    msg.animation = None
    msg.document = None
    msg.audio = None
    msg.voice = None
    msg.video_note = None
    msg.sticker = None
    msg.forward_origin = None
    msg.forward_date = None
    msg.forward_from = None
    msg.forward_from_chat = None
    msg.forward_sender_name = None
    return msg


@pytest.mark.asyncio
async def test_forwarding_from_a_to_b_no_repost_to_a(mock_bot):
    """Test that a message arriving at A enqueues to B and NEVER creates a repost for A."""
    source_chat = "-1001111111"
    target_chat = "-1002222222"
    fuid = "test_vid_abc_123"

    msg = create_mock_message(msg_id=501, chat_id=int(source_chat), chat_type="channel", text="Check https://example.com/ad", fuid=fuid)

    with patch.object(ChatRepository, "get_all_cascade_targets", new_callable=AsyncMock, return_value=[target_chat]), \
         patch.object(MediaRepository, "is_outbound_message", new_callable=AsyncMock, return_value=False), \
         patch.object(MediaRepository, "is_processed_inbound", new_callable=AsyncMock, return_value=False), \
         patch.object(MediaRepository, "mark_processed_inbound", new_callable=AsyncMock, return_value=True), \
         patch.object(MediaRepository, "add_forward_seen_and_enqueue", new_callable=AsyncMock, return_value=True) as mock_enqueue, \
         patch.object(MediaRepository, "enqueue_batch", new_callable=AsyncMock) as mock_enqueue_batch:

        should_delete = await MediaService.process_incoming_message(msg, mock_bot.id)

        # 1. Enqueued to Target B
        mock_enqueue.assert_called_once()
        args, kwargs = mock_enqueue.call_args
        assert args[0] == target_chat
        assert args[1]["tid"] == target_chat
        assert args[1]["fuid"] == fuid

        # 2. Never enqueued a local self-cleaning copy for Channel A
        mock_enqueue_batch.assert_not_called()

        # 3. In channels, should_delete is False
        assert should_delete is False


@pytest.mark.asyncio
async def test_bot_outbound_echo_is_completely_ignored(mock_bot):
    """Test that when the bot's own posted message update arrives back, it is dropped immediately."""
    chat_id = "-1002222222"
    msg = create_mock_message(msg_id=888, chat_id=int(chat_id), chat_type="channel", fuid="fuid_echo_999")

    with patch.object(MediaRepository, "is_outbound_message", new_callable=AsyncMock, return_value=True), \
         patch.object(MediaRepository, "add_forward_seen_and_enqueue", new_callable=AsyncMock) as mock_enqueue:

        res = await MediaService.process_incoming_message(msg, mock_bot.id)
        assert res is False
        mock_enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_inbound_is_ignored(mock_bot):
    """Test that an already-processed message ID or file_unique_id is ignored."""
    chat_id = "-1001111111"
    msg = create_mock_message(msg_id=502, chat_id=int(chat_id), chat_type="channel", fuid="fuid_dupe_1")

    with patch.object(MediaRepository, "is_outbound_message", new_callable=AsyncMock, return_value=False), \
         patch.object(MediaRepository, "is_processed_inbound", new_callable=AsyncMock, return_value=True), \
         patch.object(MediaRepository, "add_forward_seen_and_enqueue", new_callable=AsyncMock) as mock_enqueue:

        res = await MediaService.process_incoming_message(msg, mock_bot.id)
        assert res is False
        mock_enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_private_chat_desourcing(mock_bot):
    """Test that a forwarded media sent in private chat is enqueued cleanly back to the user without source."""
    user_id = 7975947295
    fuid = "private_test_fuid_1"
    msg = create_mock_message(msg_id=701, chat_id=user_id, chat_type="private", text="Original ad text", fuid=fuid)

    with patch.object(ChatRepository, "get_all_cascade_targets", new_callable=AsyncMock, return_value=[]), \
         patch.object(MediaRepository, "is_outbound_message", new_callable=AsyncMock, return_value=False), \
         patch.object(MediaRepository, "is_processed_inbound", new_callable=AsyncMock, return_value=False), \
         patch.object(MediaRepository, "mark_processed_inbound", new_callable=AsyncMock, return_value=True), \
         patch.object(MediaRepository, "add_forward_seen_and_enqueue", new_callable=AsyncMock, return_value=True) as mock_enqueue:

        should_delete = await MediaService.process_incoming_message(msg, mock_bot.id)

        # Enqueued directly back to the private chat ID
        mock_enqueue.assert_called_once()
        args, _ = mock_enqueue.call_args
        assert args[0] == str(user_id)
        assert args[1]["tid"] == str(user_id)
        assert args[1]["prio"] == 10
        assert should_delete is False  # Not deleting in PM


@pytest.mark.asyncio
async def test_channel_forwarded_message_desourcing(mock_bot):
    """Test that manually forwarding into a source channel triggers de-sourcing in-place and deletion of forward."""
    source_chat = "-1001111111"
    target_chat = "-1002222222"
    fuid = "fuid_manual_fwd_1"

    msg = create_mock_message(msg_id=801, chat_id=int(source_chat), chat_type="channel", text="Ad caption", fuid=fuid)
    msg.forward_origin = MagicMock()  # Mark as forwarded from elsewhere

    with patch.object(ChatRepository, "get_all_cascade_targets", new_callable=AsyncMock, return_value=[target_chat]), \
         patch.object(MediaRepository, "is_outbound_message", new_callable=AsyncMock, return_value=False), \
         patch.object(MediaRepository, "is_processed_inbound", new_callable=AsyncMock, return_value=False), \
         patch.object(MediaRepository, "mark_processed_inbound", new_callable=AsyncMock, return_value=True), \
         patch.object(MediaRepository, "add_forward_seen_and_enqueue", new_callable=AsyncMock, return_value=True) as mock_enqueue:

        should_delete = await MediaService.process_incoming_message(msg, mock_bot.id)

        # Enqueued to both target AND in-place to source channel
        assert mock_enqueue.call_count == 2
        calls = mock_enqueue.call_args_list
        target_cids = [c[0][0] for c in calls]
        assert target_chat in target_cids
        assert source_chat in target_cids

        # Should delete the manual forwarded post in the channel so only clean version remains
        assert should_delete is True


