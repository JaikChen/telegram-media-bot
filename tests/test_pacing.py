import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from src.bot.domain.forwarding import ForwardingService


@pytest.mark.asyncio
async def test_wait_per_chat_pacing():
    ForwardingService._last_send_per_chat.clear()
    chat_id = "test_chat_123"

    start = time.time()
    await ForwardingService._wait_per_chat_pacing(chat_id, min_interval=0.2)
    first_elapsed = time.time() - start
    assert first_elapsed < 0.1  # First call should be immediate

    start = time.time()
    await ForwardingService._wait_per_chat_pacing(chat_id, min_interval=0.2)
    second_elapsed = time.time() - start
    assert second_elapsed >= 0.15  # Second call should wait for pacing (~0.2s)


@pytest.mark.asyncio
async def test_process_single_forward_immediate_deletion():
    bot = AsyncMock()
    sent_msg = MagicMock()
    sent_msg.message_id = 999
    bot.send_photo.return_value = sent_msg

    with patch("src.bot.domain.forwarding.VoteRepository.is_voting_enabled", new_callable=AsyncMock, return_value=False), \
         patch("src.bot.domain.forwarding.MediaRepository.delete_queue_items", new_callable=AsyncMock) as mock_delete, \
         patch("src.bot.domain.forwarding.MediaRepository.log_forward", side_effect=Exception("Logging DB error")):

        success = await ForwardingService._process_single_forward(
            bot=bot,
            rid=101,
            tcid="-100123456",
            mt="photo",
            fid="file_id_abc",
            cap="Test caption",
            sp=0,
            fuid="fuid_abc",
            prio=5,
            scid="-100999999",
            smid="500",
        )

        assert success is True
        # delete_queue_items should have been called despite log_forward throwing an exception
        mock_delete.assert_called_once_with([101])
