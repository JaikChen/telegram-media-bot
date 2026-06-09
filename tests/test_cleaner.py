import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from src.cleaner.engine import clean_caption, restore_all_tags, strip_hidden_chars

def test_strip_hidden_chars():
    text = "Hello\u200bWorld\uFEFF!"
    assert strip_hidden_chars(text) == "HelloWorld!"

def test_restore_all_tags():
    original = "Hello #world and #python"
    cleaned = "Hello"
    restored = restore_all_tags(original, cleaned)
    assert "#world" in restored
    assert "#python" in restored
    
    # Test no duplicate
    cleaned_with_tag = "Hello #world"
    restored_2 = restore_all_tags(original, cleaned_with_tag)
    assert restored_2.count("#world") == 1
    assert "#python" in restored_2

@pytest.mark.asyncio
async def test_clean_caption_keep_all():
    with patch("src.bot.data.repositories.ChatRepository.get_chat_rules", AsyncMock(return_value=["keep_all"])), \
         patch("src.bot.data.repositories.ChatRepository.get_replacements", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_keywords", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_footer", AsyncMock(return_value=None)):
        
        text = "https://t.me/scam"
        result = await clean_caption(text, "123")
        assert result == text

@pytest.mark.asyncio
async def test_clean_caption_clean_links():
    with patch("src.bot.data.repositories.ChatRepository.get_chat_rules", AsyncMock(return_value=["clean_links"])), \
         patch("src.bot.data.repositories.ChatRepository.get_replacements", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_keywords", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_footer", AsyncMock(return_value=None)):
        
        text = "Join us at https://t.me/scam now!"
        result = await clean_caption(text, "123")
        assert "https://t.me/scam" not in result
        assert "Join us at" in result

@pytest.mark.asyncio
async def test_clean_caption_replacements():
    with patch("src.bot.data.repositories.ChatRepository.get_chat_rules", AsyncMock(return_value=["keep_all"])), \
         patch("src.bot.data.repositories.ChatRepository.get_replacements", AsyncMock(return_value=[("apple", "orange")])), \
         patch("src.bot.data.repositories.ChatRepository.get_keywords", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_footer", AsyncMock(return_value=None)):
        
        text = "I like apple"
        result = await clean_caption(text, "123")
        assert result == "I like orange"

if __name__ == "__main__":
    pytest.main([__file__])
