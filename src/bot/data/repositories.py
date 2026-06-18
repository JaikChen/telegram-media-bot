import time
import logging
from typing import List, Optional, Tuple, Any
from src.bot.data.database import db_manager

logger = logging.getLogger(__name__)


async def execute_sql(sql: str, args: tuple = (), **kwargs) -> Any:
    return await db_manager.execute(sql, args, **kwargs)


class MediaRepository:
    """Handles all persistence logic for media, deduplication, and queues."""

    @staticmethod
    async def add_seen_atomic(chat_id: str, file_unique_id: str) -> bool:
        sql = "INSERT OR IGNORE INTO seen (chat_id, file_unique_id, created_at) VALUES (?, ?, ?)"
        count = await execute_sql(sql, (chat_id, file_unique_id, int(time.time())), commit=True)
        return count > 0

    @staticmethod
    async def add_forward_seen_atomic(chat_id: str, file_unique_id: str) -> bool:
        sql = "INSERT OR IGNORE INTO forward_seen (chat_id, file_unique_id, created_at) VALUES (?, ?, ?)"
        count = await execute_sql(sql, (chat_id, file_unique_id, int(time.time())), commit=True)
        return count > 0

    @staticmethod
    async def add_forward_seen_and_enqueue(target_chat_id: str, item: dict, delay_offset: int = 0) -> bool:
        async with db_manager._write_lock:
            db = await db_manager.get_db()
            try:
                # Check if already forwarded or seen in the target chat (Global Deduplication)
                sql_check = """
                    SELECT 1 FROM seen WHERE chat_id=? AND file_unique_id=?
                    UNION
                    SELECT 1 FROM forward_seen WHERE chat_id=? AND file_unique_id=?
                    LIMIT 1
                """
                async with db.execute(
                    sql_check, (target_chat_id, item["fuid"], target_chat_id, item["fuid"])
                ) as cursor:
                    if await cursor.fetchone():
                        logger.info(f"♻️ [Deduplicated] Media {item['fuid']} already exists in target {target_chat_id}")
                        return False

                now = int(time.time())
                await db.execute(
                    "INSERT INTO forward_seen (chat_id, file_unique_id, created_at) VALUES (?, ?, ?)",
                    (target_chat_id, item["fuid"], now),
                )

                sql_q = """INSERT INTO forward_queue 
                         (target_chat_id, media_type, file_id, caption, has_spoiler, 
                          file_unique_id, media_group_id, created_at, priority, 
                          source_chat_id, source_msg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                args_q = (
                    target_chat_id,
                    item["mt"],
                    item["fid"],
                    item.get("cap"),
                    1 if item.get("sp") else 0,
                    item["fuid"],
                    item.get("mgid"),
                    now + delay_offset,
                    item.get("prio", 0),
                    item.get("scid"),
                    item.get("smid"),
                )
                await db.execute(sql_q, args_q)

                await db.commit()
                return True
            except Exception as e:
                await db.rollback()
                logger.error(f"❌ Transaction Error (Single): {e}")
                raise

    @staticmethod
    async def add_forward_seen_and_enqueue_album(target_chat_id: str, items: List[dict], delay_offset: int = 0) -> bool:
        if not items:
            return True
        async with db_manager._write_lock:
            db = await db_manager.get_db()
            try:
                # Check if first item already exists in target (Global Deduplication)
                sql_check = """
                    SELECT 1 FROM seen WHERE chat_id=? AND file_unique_id=?
                    UNION
                    SELECT 1 FROM forward_seen WHERE chat_id=? AND file_unique_id=?
                    LIMIT 1
                """
                async with db.execute(
                    sql_check, (target_chat_id, items[0]["fuid"], target_chat_id, items[0]["fuid"])
                ) as cursor:
                    if await cursor.fetchone():
                        logger.info(
                            f"♻️ [Deduplicated Album] Media {items[0]['fuid']} already exists in target {target_chat_id}"
                        )
                        return False

                now = int(time.time())
                for it in items:
                    await db.execute(
                        "INSERT INTO forward_seen (chat_id, file_unique_id, created_at) VALUES (?, ?, ?)",
                        (target_chat_id, it["fuid"], now),
                    )

                    sql_q = """INSERT INTO forward_queue 
                             (target_chat_id, media_type, file_id, caption, has_spoiler, 
                              file_unique_id, media_group_id, created_at, priority, 
                              source_chat_id, source_msg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                    args_q = (
                        target_chat_id,
                        it["mt"],
                        it["fid"],
                        it.get("cap"),
                        1 if it.get("sp") else 0,
                        it["fuid"],
                        it.get("mgid"),
                        now + delay_offset,
                        it.get("prio", 0),
                        it.get("scid"),
                        it.get("smid"),
                    )
                    await db.execute(sql_q, args_q)

                await db.commit()
                return True
            except Exception as e:
                await db.rollback()
                logger.error(f"❌ Transaction Error (Album): {e}")
                raise

    @staticmethod
    async def get_forward_queue_counts() -> List[tuple]:
        """Returns counts of pending tasks grouped by target chat."""
        sql = """
            SELECT q.target_chat_id, c.title, COUNT(*) 
            FROM forward_queue q
            LEFT JOIN chats c ON q.target_chat_id = c.chat_id
            WHERE q.status = 0
            GROUP BY q.target_chat_id
            ORDER BY COUNT(*) DESC
        """
        return await execute_sql(sql, fetchall=True)

    @staticmethod
    async def enqueue_batch(items: List[dict]):
        if not items:
            return
        now = int(time.time())
        stmts = []
        for it in items:
            sql = """INSERT OR IGNORE INTO forward_queue 
                     (target_chat_id, media_type, file_id, caption, has_spoiler, 
                      file_unique_id, media_group_id, created_at, priority, 
                      source_chat_id, source_msg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            args = (
                it["tid"],
                it["mt"],
                it["fid"],
                it.get("cap"),
                1 if it.get("sp") else 0,
                it["fuid"],
                it.get("mgid"),
                now,
                it.get("prio", 0),
                it.get("scid"),
                it.get("smid"),
            )
            stmts.append((sql, args))
        await db_manager.execute_many(stmts)

    @staticmethod
    async def fetch_queue_batch(limit: int = 50) -> List[tuple]:
        """
        Atomically fetches and marks a batch of items as 'processing'.
        Compatible with older SQLite versions lacking RETURNING support.
        """
        now = int(time.time())
        # Use an explicit transaction to ensure atomic SELECT then UPDATE
        async with db_manager._write_lock:
            db = await db_manager.get_db()
            try:
                # 1. Fetch the rows first
                select_sql = """
                    SELECT * FROM forward_queue
                    WHERE (status = 0 AND created_at <= ?) OR (status = 1 AND updated_at < ?)
                    ORDER BY priority DESC, created_at ASC, id ASC
                    LIMIT ?
                """
                async with db.execute(select_sql, (now, now - 600, limit)) as cursor:
                    rows = await cursor.fetchall()

                if not rows:
                    return []

                # 2. Mark those specific rows as processing
                row_ids = [r[0] for r in rows]
                placeholders = ",".join(["?"] * len(row_ids))
                update_sql = f"""
                    UPDATE forward_queue
                    SET status = 1, updated_at = ?
                    WHERE id IN ({placeholders})
                """
                await db.execute(update_sql, (now, *row_ids))
                await db.commit()
                return rows
            except Exception as e:
                await db.rollback()
                logger.error(f"❌ Error in fetch_queue_batch transaction: {e}")
                return []

    @staticmethod
    async def get_forward_group(chat_id: str, media_group_id: str) -> List[tuple]:
        return await execute_sql(
            "SELECT * FROM forward_queue WHERE target_chat_id=? AND media_group_id=? ORDER BY id ASC",
            (chat_id, media_group_id),
            fetchall=True,
        )

    @staticmethod
    async def delete_forward_group(chat_id: str, media_group_id: str):
        await execute_sql(
            "DELETE FROM forward_queue WHERE target_chat_id=? AND media_group_id=?",
            (chat_id, media_group_id),
            commit=True,
        )

    @staticmethod
    async def delete_queue_items(ids: List[int]):
        if not ids:
            return
        placeholders = ",".join(["?"] * len(ids))
        await execute_sql(f"DELETE FROM forward_queue WHERE id IN ({placeholders})", tuple(ids), commit=True)

    @staticmethod
    async def reset_processing_status(ids: List[int]):
        if not ids:
            return
        placeholders = ",".join(["?"] * len(ids))
        await execute_sql(
            f"UPDATE forward_queue SET status = 0, updated_at = ? WHERE id IN ({placeholders})",
            (int(time.time()), *ids),
            commit=True,
        )

    @staticmethod
    async def is_duplicate_globally(chat_id: str, file_unique_id: str) -> bool:
        """Checks if a file has been seen or forwarded in a specific chat."""
        sql = """
            SELECT 1 FROM seen WHERE chat_id=? AND file_unique_id=?
            UNION
            SELECT 1 FROM forward_seen WHERE chat_id=? AND file_unique_id=?
            LIMIT 1
        """
        res = await execute_sql(sql, (chat_id, file_unique_id, chat_id, file_unique_id), fetchone=True)
        return res is not None

    @staticmethod
    async def increment_retry(rid: int, reason: str = "Unknown"):
        from src.bot.core.config import MAX_RETRY_COUNT

        await execute_sql(
            "UPDATE forward_queue SET retry_count = retry_count + 1, status = 0, updated_at = ? WHERE id = ?",
            (int(time.time()), rid),
            commit=True,
        )
        r = await execute_sql(
            "SELECT retry_count, target_chat_id, media_type, file_id, caption, has_spoiler, file_unique_id, media_group_id, source_chat_id, source_msg_id FROM forward_queue WHERE id=?",
            (rid,),
            fetchone=True,
        )
        if r and r[0] >= MAX_RETRY_COUNT:
            sql_dlq = "INSERT INTO dead_letter_queue (target_chat_id, media_type, file_id, caption, has_spoiler, file_unique_id, media_group_id, failed_at, reason, source_chat_id, source_msg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            args_dlq = (r[1], r[2], r[3], r[4], r[5], r[6], r[7], int(time.time()), reason, r[8], r[9])
            await execute_sql(sql_dlq, args_dlq, commit=True)
            await execute_sql("DELETE FROM forward_queue WHERE id=?", (rid,), commit=True)

    @staticmethod
    async def increment_retry_group(chat_id: str, media_group_id: str, reason: str = "Unknown"):
        from src.bot.core.config import MAX_RETRY_COUNT

        rows = await MediaRepository.get_forward_group(chat_id, media_group_id)
        if not rows:
            return
        if rows[0][9] + 1 >= MAX_RETRY_COUNT:
            now = int(time.time())
            stmts = []
            for r in rows:
                sql = "INSERT INTO dead_letter_queue (target_chat_id, media_type, file_id, caption, has_spoiler, file_unique_id, media_group_id, failed_at, reason, source_chat_id, source_msg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                args = (r[1], r[2], r[3], r[4], r[5], r[6], r[7], now, reason, r[11], r[12])
                stmts.append((sql, args))
            stmts.append(
                ("DELETE FROM forward_queue WHERE target_chat_id=? AND media_group_id=?", (chat_id, media_group_id))
            )
            await db_manager.execute_many(stmts)
        else:
            await execute_sql(
                "UPDATE forward_queue SET retry_count = retry_count + 1, status = 0, updated_at = ? WHERE target_chat_id=? AND media_group_id=?",
                (int(time.time()), chat_id, media_group_id),
                commit=True,
            )

    @staticmethod
    async def is_forward_paused() -> bool:
        r = await execute_sql("SELECT value FROM global_settings WHERE key='forward_paused'", fetchone=True)
        return r is not None and r[0] == "1"

    @staticmethod
    async def set_forward_paused(paused: bool):
        await execute_sql(
            "INSERT OR REPLACE INTO global_settings (key, value) VALUES ('forward_paused', ?)",
            ("1" if paused else "0",),
            commit=True,
        )

    @staticmethod
    async def get_delay_settings() -> Tuple[int, int]:
        from src.bot.core.config import DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX

        r = await execute_sql("SELECT min_delay, max_delay FROM forward_settings LIMIT 1", fetchone=True)
        return (r[0], r[1]) if r else (DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX)

    @staticmethod
    async def set_delay_settings(min_s: int, max_s: int):
        await execute_sql("DELETE FROM forward_settings", commit=True)
        await execute_sql(
            "INSERT INTO forward_settings (min_delay, max_delay) VALUES (?, ?)", (min_s, max_s), commit=True
        )

    @staticmethod
    async def peek_queue() -> Optional[tuple]:
        return await execute_sql(
            "SELECT * FROM forward_queue WHERE status = 0 OR (status = 1 AND updated_at < ?) ORDER BY priority DESC, id ASC LIMIT 1",
            (int(time.time()) - 600,),
            fetchone=True,
        )

    @staticmethod
    async def get_stats() -> List[tuple]:
        sql = "SELECT chat_id, COUNT(*) FROM seen GROUP BY chat_id ORDER BY COUNT(*) DESC"
        return await execute_sql(sql, fetchall=True)

    @staticmethod
    async def clean_expired_data(days: int = 365) -> int:
        cutoff = int(time.time()) - (days * 86400)
        res = await execute_sql("DELETE FROM seen WHERE created_at < ?", (cutoff,), commit=True)
        return res if isinstance(res, int) else 0

    @staticmethod
    async def vacuum_db():
        await execute_sql("VACUUM", commit=True)

    @staticmethod
    async def log_forward(source_chat_id: str, source_msg_id: str, target_chat_id: str, target_msg_id: str):
        sql = "INSERT OR REPLACE INTO forward_log (source_chat_id, source_msg_id, target_chat_id, target_msg_id, created_at) VALUES (?, ?, ?, ?, ?)"
        await execute_sql(
            sql, (source_chat_id, source_msg_id, target_chat_id, target_msg_id, int(time.time())), commit=True
        )

    @staticmethod
    async def get_forwarded_targets(source_chat_id: str, source_msg_id: str) -> List[tuple]:
        return await execute_sql(
            "SELECT target_chat_id, target_msg_id FROM forward_log WHERE source_chat_id=? AND source_msg_id=?",
            (source_chat_id, source_msg_id),
            fetchall=True,
        )

    @staticmethod
    async def get_log_channel_global() -> Optional[str]:
        r = await execute_sql("SELECT value FROM global_settings WHERE key='log_channel'", fetchone=True)
        return r[0] if r else None

    @staticmethod
    async def set_log_channel_global(log_cid: str):
        await execute_sql(
            "INSERT OR REPLACE INTO global_settings (key, value) VALUES ('log_channel', ?)", (log_cid,), commit=True
        )


class VoteRepository:
    """Handles voting settings and data."""

    @staticmethod
    async def is_voting_enabled(chat_id: str) -> bool:
        r = await execute_sql("SELECT is_enabled FROM vote_settings WHERE chat_id=?", (chat_id,), fetchone=True)
        return r is not None and r[0] == 1

    @staticmethod
    async def set_voting_enabled(chat_id: str, enabled: bool):
        await execute_sql(
            "INSERT OR REPLACE INTO vote_settings (chat_id, is_enabled) VALUES (?, ?)",
            (chat_id, 1 if enabled else 0),
            commit=True,
        )

    @staticmethod
    async def get_vote_counts(chat_id: str, message_id: str) -> Tuple[int, int]:
        rows = await execute_sql(
            "SELECT vote_type, COUNT(*) FROM votes WHERE chat_id=? AND message_id=? GROUP BY vote_type",
            (chat_id, message_id),
            fetchall=True,
        )
        counts = {"up": 0, "down": 0}
        for r in rows:
            if r[0] in counts:
                counts[r[0]] = r[1]
        return counts["up"], counts["down"]

    @staticmethod
    async def add_vote(chat_id: str, message_id: str, user_id: str, vote_type: str):
        await execute_sql(
            "INSERT OR REPLACE INTO votes (chat_id, message_id, user_id, vote_type) VALUES (?, ?, ?, ?)",
            (chat_id, message_id, user_id, vote_type),
            commit=True,
        )

    @staticmethod
    async def remove_vote(chat_id: str, message_id: str, user_id: str):
        await execute_sql(
            "DELETE FROM votes WHERE chat_id=? AND message_id=? AND user_id=?",
            (chat_id, message_id, user_id),
            commit=True,
        )

    @staticmethod
    async def get_user_vote(chat_id: str, message_id: str, user_id: str) -> Optional[str]:
        r = await execute_sql(
            "SELECT vote_type FROM votes WHERE chat_id=? AND message_id=? AND user_id=?",
            (chat_id, message_id, user_id),
            fetchone=True,
        )
        return r[0] if r else None


class AdminRepository:
    """Handles dynamic administrator management."""

    @staticmethod
    async def list_admins() -> List[str]:
        rows = await execute_sql("SELECT user_id FROM admins", fetchall=True)
        return [r[0] for r in rows]

    @staticmethod
    async def add_admin(user_id: str):
        await execute_sql("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,), commit=True)

    @staticmethod
    async def delete_admin(user_id: str):
        await execute_sql("DELETE FROM admins WHERE user_id=?", (user_id,), commit=True)


class ChatRepository:
    """Handles chat settings and rules."""

    @staticmethod
    async def save_chat(chat_id: str, title: str):
        await execute_sql("INSERT OR REPLACE INTO chats (chat_id, title) VALUES (?, ?)", (chat_id, title), commit=True)

    @staticmethod
    async def get_forward_targets(source_chat_id: str) -> List[str]:
        rows = await execute_sql(
            "SELECT target_chat_id FROM forward_map WHERE source_chat_id=?", (source_chat_id,), fetchall=True
        )
        return [r[0] for r in rows]

    @staticmethod
    async def get_chat_rules(chat_id: str) -> List[str]:
        rows = await execute_sql("SELECT rule FROM rules WHERE chat_id=?", (chat_id,), fetchall=True)
        return [r[0] for r in rows]

    @staticmethod
    async def get_keywords(chat_id: str) -> List[Tuple[str, bool]]:
        rows = await execute_sql("SELECT word, is_regex FROM keywords WHERE chat_id=?", (chat_id,), fetchall=True)
        return [(r[0], bool(r[1])) for r in rows]

    @staticmethod
    async def get_replacements(chat_id: str) -> List[Tuple[str, str]]:
        return await execute_sql(
            "SELECT old_word, new_word FROM replacements WHERE chat_id=?", (chat_id,), fetchall=True
        )

    @staticmethod
    async def get_footer(chat_id: str) -> Optional[str]:
        r = await execute_sql("SELECT text FROM footers WHERE chat_id=?", (chat_id,), fetchone=True)
        return r[0] if r else None

    @staticmethod
    async def is_user_whitelisted(chat_id: str, user_id: str) -> bool:
        r = await execute_sql(
            "SELECT 1 FROM user_whitelist WHERE chat_id=? AND user_id=?", (chat_id, user_id), fetchone=True
        )
        return r is not None

    @staticmethod
    async def get_chat_whitelist(chat_id: str) -> List[str]:
        rows = await execute_sql("SELECT user_id FROM user_whitelist WHERE chat_id=?", (chat_id,), fetchall=True)
        return [r[0] for r in rows]

    @staticmethod
    async def get_triggers(chat_id: str) -> List[Tuple[str, str]]:
        return await execute_sql(
            "SELECT trigger_word, response_text FROM triggers WHERE chat_id=?", (chat_id,), fetchall=True
        )

    @staticmethod
    async def get_log_channel(chat_id: str) -> Optional[str]:
        r = await execute_sql("SELECT log_channel FROM log_settings WHERE chat_id=?", (chat_id,), fetchone=True)
        return r[0] if r else None

    @staticmethod
    async def set_log_channel(chat_id: str, log_cid: str):
        await execute_sql(
            "INSERT OR REPLACE INTO log_settings (chat_id, log_channel) VALUES (?, ?)", (chat_id, log_cid), commit=True
        )

    @staticmethod
    async def get_log_filter(chat_id: str) -> List[str]:
        r = await execute_sql("SELECT categories FROM log_filters WHERE chat_id=?", (chat_id,), fetchone=True)
        return r[0].split(",") if r and r[0] else []

    @staticmethod
    async def set_log_filter(chat_id: str, categories: List[str]):
        await execute_sql(
            "INSERT OR REPLACE INTO log_filters (chat_id, categories) VALUES (?, ?)",
            (chat_id, ",".join(categories)),
            commit=True,
        )

    @staticmethod
    async def get_quiet_mode(chat_id: str) -> Optional[str]:
        r = await execute_sql("SELECT mode FROM quiet_settings WHERE chat_id=?", (chat_id,), fetchone=True)
        return r[0] if r else "off"

    @staticmethod
    async def set_quiet_mode(chat_id: str, mode: str):
        await execute_sql(
            "INSERT OR REPLACE INTO quiet_settings (chat_id, mode) VALUES (?, ?)", (chat_id, mode), commit=True
        )

    @staticmethod
    async def is_locked(chat_id: str) -> bool:
        r = await execute_sql("SELECT is_locked FROM chat_locks WHERE chat_id=?", (chat_id,), fetchone=True)
        return r is not None and r[0] == 1

    @staticmethod
    async def get_media_filter(chat_id: str) -> List[str]:
        r = await execute_sql("SELECT allowed_types FROM media_filters WHERE chat_id=?", (chat_id,), fetchone=True)
        return r[0].split(",") if r and r[0] else []

    @staticmethod
    async def set_media_filter(chat_id: str, types: List[str]):
        await execute_sql(
            "INSERT OR REPLACE INTO media_filters (chat_id, allowed_types) VALUES (?, ?)",
            (chat_id, ",".join(types)),
            commit=True,
        )

    @staticmethod
    async def get_all_chat_ids() -> List[str]:
        rows = await execute_sql("SELECT chat_id FROM chats", fetchall=True)
        return [r[0] for r in rows]

    @staticmethod
    async def add_rule(chat_id: str, rule: str):
        await execute_sql("INSERT OR IGNORE INTO rules (chat_id, rule) VALUES (?, ?)", (chat_id, rule), commit=True)

    @staticmethod
    async def delete_rule(chat_id: str, rule: str):
        await execute_sql("DELETE FROM rules WHERE chat_id=? AND rule=?", (chat_id, rule), commit=True)

    @staticmethod
    async def clear_rules(chat_id: str):
        await execute_sql("DELETE FROM rules WHERE chat_id=?", (chat_id,), commit=True)

    @staticmethod
    async def add_keyword(chat_id: str, word: str, is_regex: bool = False):
        await execute_sql(
            "INSERT OR REPLACE INTO keywords (chat_id, word, is_regex) VALUES (?, ?, ?)",
            (chat_id, word, 1 if is_regex else 0),
            commit=True,
        )

    @staticmethod
    async def delete_keyword(chat_id: str, word: str):
        await execute_sql("DELETE FROM keywords WHERE chat_id=? AND word=?", (chat_id, word), commit=True)

    @staticmethod
    async def add_replacement(chat_id: str, old: str, new: str):
        await execute_sql(
            "INSERT OR REPLACE INTO replacements (chat_id, old_word, new_word) VALUES (?, ?, ?)",
            (chat_id, old, new),
            commit=True,
        )

    @staticmethod
    async def delete_replacement(chat_id: str, old: str):
        await execute_sql("DELETE FROM replacements WHERE chat_id=? AND old_word=?", (chat_id, old), commit=True)

    @staticmethod
    async def set_footer(chat_id: str, text: str):
        await execute_sql("INSERT OR REPLACE INTO footers (chat_id, text) VALUES (?, ?)", (chat_id, text), commit=True)

    @staticmethod
    async def delete_footer(chat_id: str):
        await execute_sql("DELETE FROM footers WHERE chat_id=?", (chat_id,), commit=True)

    @staticmethod
    async def lock_chat(chat_id: str):
        await execute_sql(
            "INSERT OR REPLACE INTO chat_locks (chat_id, is_locked) VALUES (?, 1)", (chat_id,), commit=True
        )

    @staticmethod
    async def unlock_chat(chat_id: str):
        await execute_sql(
            "INSERT OR REPLACE INTO chat_locks (chat_id, is_locked) VALUES (?, 0)", (chat_id,), commit=True
        )

    @staticmethod
    async def list_all_forwards() -> List[Tuple[str, str]]:
        """List all source-to-target forwarding pairs."""
        return await execute_sql("SELECT source_chat_id, target_chat_id FROM forward_map", fetchall=True)

    @staticmethod
    async def add_forward(source: str, target: str):
        await execute_sql(
            "INSERT OR IGNORE INTO forward_map (source_chat_id, target_chat_id) VALUES (?, ?)",
            (source, target),
            commit=True,
        )

    @staticmethod
    async def del_forward(source: str, target: str):
        await execute_sql(
            "DELETE FROM forward_map WHERE source_chat_id=? AND target_chat_id=?", (source, target), commit=True
        )

    @staticmethod
    async def list_forward(source: str) -> List[str]:
        rows = await execute_sql(
            "SELECT target_chat_id FROM forward_map WHERE source_chat_id=?", (source,), fetchall=True
        )
        return [r[0] for r in rows]

    @staticmethod
    async def add_user_whitelist(chat_id: str, user_id: str):
        await execute_sql(
            "INSERT OR IGNORE INTO user_whitelist (chat_id, user_id) VALUES (?, ?)", (chat_id, user_id), commit=True
        )

    @staticmethod
    async def del_user_whitelist(chat_id: str, user_id: str):
        await execute_sql("DELETE FROM user_whitelist WHERE chat_id=? AND user_id=?", (chat_id, user_id), commit=True)

    @staticmethod
    async def add_trigger(chat_id: str, kw: str, text: str):
        await execute_sql(
            "INSERT OR REPLACE INTO triggers (chat_id, trigger_word, response_text) VALUES (?, ?, ?)",
            (chat_id, kw, text),
            commit=True,
        )

    @staticmethod
    async def del_trigger(chat_id: str, kw: str):
        await execute_sql("DELETE FROM triggers WHERE chat_id=? AND trigger_word=?", (chat_id, kw), commit=True)

    @staticmethod
    async def get_caption_template(chat_id: str) -> Optional[str]:
        r = await execute_sql("SELECT template FROM caption_templates WHERE chat_id=?", (chat_id,), fetchone=True)
        return r[0] if r else None

    @staticmethod
    async def set_caption_template(chat_id: str, template: str):
        await execute_sql(
            "INSERT OR REPLACE INTO caption_templates (chat_id, template) VALUES (?, ?)",
            (chat_id, template),
            commit=True,
        )

    @staticmethod
    async def delete_caption_template(chat_id: str):
        await execute_sql("DELETE FROM caption_templates WHERE chat_id=?", (chat_id,), commit=True)
