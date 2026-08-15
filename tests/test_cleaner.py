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
    with patch("src.bot.data.repositories.ChatRepository.get_chat_rules", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_replacements", AsyncMock(return_value=[("apple", "orange")])), \
         patch("src.bot.data.repositories.ChatRepository.get_keywords", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_footer", AsyncMock(return_value=None)), \
         patch("src.bot.data.repositories.ChatRepository.get_caption_template", AsyncMock(return_value=None)):

        text = "I like apple"
        result = await clean_caption(text, "123")
        assert result == "I like orange"


@pytest.mark.asyncio
async def test_clean_caption_strip_all_if_links():
    with patch("src.bot.data.repositories.ChatRepository.get_chat_rules", AsyncMock(return_value=["strip_all_if_links"])), \
         patch("src.bot.data.repositories.ChatRepository.get_replacements", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_keywords", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_footer", AsyncMock(return_value=None)), \
         patch("src.bot.data.repositories.ChatRepository.get_caption_template", AsyncMock(return_value=None)):

        text = "Check out https://example.com for info"
        result = await clean_caption(text, "123")
        assert result == ""


@pytest.mark.asyncio
async def test_clean_caption_block_keywords():
    with patch("src.bot.data.repositories.ChatRepository.get_chat_rules", AsyncMock(return_value=["block_keywords"])), \
         patch("src.bot.data.repositories.ChatRepository.get_replacements", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_keywords", AsyncMock(return_value=[("spam", False)])), \
         patch("src.bot.data.repositories.ChatRepository.get_footer", AsyncMock(return_value=None)), \
         patch("src.bot.data.repositories.ChatRepository.get_caption_template", AsyncMock(return_value=None)):

        text = "This is a spam message"
        result = await clean_caption(text, "123")
        assert result == ""


@pytest.mark.asyncio
async def test_clean_caption_maxlen():
    with patch("src.bot.data.repositories.ChatRepository.get_chat_rules", AsyncMock(return_value=["maxlen:10"])), \
         patch("src.bot.data.repositories.ChatRepository.get_replacements", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_keywords", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_footer", AsyncMock(return_value=None)), \
         patch("src.bot.data.repositories.ChatRepository.get_caption_template", AsyncMock(return_value=None)):

        text = "Hello World Extra Text"
        result = await clean_caption(text, "123")
        assert result == "Hello Worl"


@pytest.mark.asyncio
async def test_clean_caption_pangu():
    with patch("src.bot.data.repositories.ChatRepository.get_chat_rules", AsyncMock(return_value=["pangu"])), \
         patch("src.bot.data.repositories.ChatRepository.get_replacements", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_keywords", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_footer", AsyncMock(return_value=None)), \
         patch("src.bot.data.repositories.ChatRepository.get_caption_template", AsyncMock(return_value=None)):

        text = "中文iOS测试123"
        result = await clean_caption(text, "123")
        assert result == "中文 iOS 测试 123"


@pytest.mark.asyncio
async def test_clean_caption_clean_keywords_line_by_line():
    with patch("src.bot.data.repositories.ChatRepository.get_chat_rules", AsyncMock(return_value=["clean_keywords"])), \
         patch("src.bot.data.repositories.ChatRepository.get_replacements", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_keywords", AsyncMock(return_value=[("广告", False), (r"代开\w+", True)])), \
         patch("src.bot.data.repositories.ChatRepository.get_footer", AsyncMock(return_value=None)), \
         patch("src.bot.data.repositories.ChatRepository.get_caption_template", AsyncMock(return_value=None)):

        text = "第一行正文\n这是广告请忽略\n代开会员点此\n最后一行正文"
        result = await clean_caption(text, "123")
        assert result == "第一行正文\n最后一行正文"


@pytest.mark.asyncio
async def test_clean_caption_markdown_links():
    with patch("src.bot.data.repositories.ChatRepository.get_chat_rules", AsyncMock(return_value=["clean_links"])), \
         patch("src.bot.data.repositories.ChatRepository.get_replacements", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_keywords", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_footer", AsyncMock(return_value=None)), \
         patch("src.bot.data.repositories.ChatRepository.get_caption_template", AsyncMock(return_value=None)):

        text = "精彩视频 [点击加入频道](https://t.me/mychannel) 欢迎关注"
        result = await clean_caption(text, "123")
        assert "https://t.me" not in result
        assert "点击加入频道" in result


def test_restore_all_tags_filters_ad_tags():
    original = "正文内容 #好物 #博彩 #代开"
    cleaned = "正文内容"
    keywords = [("博彩", False), ("代开", False)]
    restored = restore_all_tags(original, cleaned, keywords=keywords)
    assert "#好物" in restored
    assert "#博彩" not in restored
    assert "#代开" not in restored


def test_restore_all_tags_empty_when_caption_wiped():
    original = "全广告 #博彩 #广告"
    cleaned = ""
    restored = restore_all_tags(original, cleaned)
    assert restored == ""


@pytest.mark.asyncio
async def test_clean_caption_strip_ad_lines():
    with patch("src.bot.data.repositories.ChatRepository.get_chat_rules", AsyncMock(return_value=["strip_ad_lines"])), \
         patch("src.bot.data.repositories.ChatRepository.get_replacements", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_keywords", AsyncMock(return_value=[("博彩", False), (r"代开\w+", True)])), \
         patch("src.bot.data.repositories.ChatRepository.get_footer", AsyncMock(return_value=None)), \
         patch("src.bot.data.repositories.ChatRepository.get_caption_template", AsyncMock(return_value=None)):

        text = (
            "精彩大片推荐\n"
            "导演：张三\n"
            "主演：李四\n"
            "关注频道：https://t.me/mychannel\n"
            "官方账号：@mychannel_bot 欢迎体验\n"
            "加入VIP博彩群请联系客服\n"
            "高清无码 经典回顾"
        )
        result = await clean_caption(text, "123")
        expected = (
            "精彩大片推荐\n"
            "导演：张三\n"
            "主演：李四\n"
            "高清无码 经典回顾"
        )
        assert result == expected


@pytest.mark.asyncio
async def test_clean_caption_comment_leads_ads():
    with patch("src.bot.data.repositories.ChatRepository.get_chat_rules", AsyncMock(return_value=["strip_ad_lines"])), \
         patch("src.bot.data.repositories.ChatRepository.get_replacements", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_keywords", AsyncMock(return_value=[])), \
         patch("src.bot.data.repositories.ChatRepository.get_footer", AsyncMock(return_value=None)), \
         patch("src.bot.data.repositories.ChatRepository.get_caption_template", AsyncMock(return_value=None)):

        text = (
            "第08集 绝密行动\n"
            "> 103p4v-评论区看全集。\n"
            "剧情介绍：卧底潜伏成功\n"
            "评论区置顶获取完整版\n"
            "全网独家 高清首发"
        )
        result = await clean_caption(text, "123")
        expected = (
            "第08集 绝密行动\n"
            "剧情介绍：卧底潜伏成功\n"
            "全网独家 高清首发"
        )
        assert result == expected


if __name__ == "__main__":
    pytest.main([__file__])



