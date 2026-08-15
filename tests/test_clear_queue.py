import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.bot.data.repositories import MediaRepository
from src.bot.handlers.sys_admin import handle_clear_queue


@pytest.mark.asyncio
async def test_clear_forward_queue_db():
    with patch("src.bot.data.repositories.execute_sql") as mock_exec:
        mock_exec.side_effect = [
            (5,),   # SELECT COUNT(*) for all
            None,   # DELETE FROM forward_queue
            (3,),   # SELECT COUNT(*) for specific chat
            None,   # DELETE FROM forward_queue WHERE target_chat_id=?
        ]

        # Test clear all
        count_all = await MediaRepository.clear_forward_queue("all")
        assert count_all == 5

        # Test clear specific chat
        count_chat = await MediaRepository.clear_forward_queue("-1001234567")
        assert count_chat == 3


@pytest.mark.asyncio
async def test_handle_clear_queue_handler():
    update = MagicMock()
    update.message = AsyncMock()
    update.effective_user.id = 7975947295
    update.message.from_user.id = 7975947295

    context = MagicMock()
    context.args = ["all"]

    with patch("src.bot.handlers.sys_admin.is_global_admin", return_value=True), \
         patch("src.bot.handlers.sys_admin.MediaRepository.clear_forward_queue", new_callable=AsyncMock, return_value=12), \
         patch("src.bot.handlers.sys_admin.log_event", new_callable=AsyncMock):

        await handle_clear_queue(update, context)

        update.message.reply_text.assert_called_once()
        assert "12" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_help_success():
    from src.bot.handlers.info import handle_help

    update = MagicMock()
    update.message = AsyncMock()
    update.message.from_user.id = 7975947295
    update.effective_user.id = 7975947295
    context = MagicMock()

    with patch("src.bot.handlers.info.MediaRepository.get_delay_settings", new_callable=AsyncMock, return_value=(10, 60)), \
         patch("src.bot.handlers.info.is_admin", new_callable=AsyncMock, return_value=True):
        await handle_help(update, context)
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "Super Admin" in text
        assert "/clearqueue" in text

