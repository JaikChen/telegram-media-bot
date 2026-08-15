import pytest
import uuid
import asyncio
from src.bot.data.database import db_manager
from src.bot.data.repositories import MediaRepository


@pytest.mark.asyncio
async def test_atomic_deduplication():
    """Verify that media_dedup_log prevents duplicate enqueue of identical media to the same target chat."""
    await db_manager.get_db()
    target_chat = f"-100{uuid.uuid4().int % 1000000000}"
    fuid = f"test_fuid_{uuid.uuid4()}"

    item = {
        "tid": target_chat,
        "mt": "photo",
        "fid": "fid_atomic_001",
        "cap": "Test Caption",
        "sp": False,
        "fuid": fuid,
        "prio": 5,
        "scid": "-100111",
        "smid": "100",
    }

    # First enqueue attempt -> should succeed
    res1 = await MediaRepository.add_forward_seen_and_enqueue(target_chat, item)
    assert res1 is True

    # Second enqueue attempt with same target & fuid -> should be deduplicated (False)
    res2 = await MediaRepository.add_forward_seen_and_enqueue(target_chat, item)
    assert res2 is False


@pytest.mark.asyncio
async def test_atomic_album_deduplication():
    """Verify album deduplication filters out items that already exist in target chat."""
    await db_manager.get_db()
    target_chat = f"-100{uuid.uuid4().int % 1000000000}"
    uid_1 = f"fuid_alb_{uuid.uuid4()}"
    uid_2 = f"fuid_alb_{uuid.uuid4()}"
    gid = f"grp_{uuid.uuid4()}"

    items = [
        {"tid": target_chat, "mt": "photo", "fid": "fid_alb_1", "cap": "Cap 1", "sp": False, "fuid": uid_1, "mgid": gid},
        {"tid": target_chat, "mt": "photo", "fid": "fid_alb_2", "cap": None, "sp": False, "fuid": uid_2, "mgid": gid},
    ]

    # First attempt -> all 2 items enqueued
    res1 = await MediaRepository.add_forward_seen_and_enqueue_album(target_chat, items)
    assert res1 is True

    # Second attempt with same items -> returns False because all items are deduplicated
    res2 = await MediaRepository.add_forward_seen_and_enqueue_album(target_chat, items)
    assert res2 is False
