import aiosqlite
import asyncio
import logging
import contextlib
from pathlib import Path
from typing import List, Tuple, Any, Optional
from src.bot.core import config

logger = logging.getLogger(__name__)


class DatabaseManager:
    _instance = None
    _conn: Optional[aiosqlite.Connection] = None
    _write_lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    async def get_db(self) -> aiosqlite.Connection:
        if self._conn is None:
            try:
                # Ensure directory exists using Path for safety
                db_path = Path(config.DB_FILE).resolve()
                db_path.parent.mkdir(parents=True, exist_ok=True)

                self._conn = await aiosqlite.connect(str(db_path))
                await self._conn.execute("PRAGMA journal_mode=WAL;")
                await self._conn.execute("PRAGMA synchronous=NORMAL;")
                await self._conn.commit()
                logger.info(f"🔌 Database connected: {db_path.name} (WAL Mode)")

                # Auto-initialize tables
                await self.init_db()
            except Exception as e:
                logger.error(f"❌ DB Init Error: {e}")
                raise
        return self._conn

    async def init_db(self) -> None:
        """Creates all necessary tables and indexes if they don't exist."""
        schemas = [
            # Core Tables
            """CREATE TABLE IF NOT EXISTS chats (
                chat_id TEXT PRIMARY KEY, 
                title TEXT, 
                created_at INTEGER DEFAULT (strftime('%s','now'))
            )""",
            """CREATE TABLE IF NOT EXISTS admins (
                user_id TEXT PRIMARY KEY
            )""",
            # Deduplication Tables
            """CREATE TABLE IF NOT EXISTS seen (
                chat_id TEXT, 
                file_unique_id TEXT, 
                created_at INTEGER,
                PRIMARY KEY (chat_id, file_unique_id)
            )""",
            """CREATE TABLE IF NOT EXISTS forward_seen (
                chat_id TEXT, 
                file_unique_id TEXT,
                created_at INTEGER,
                PRIMARY KEY (chat_id, file_unique_id)
            )""",
            # Forwarding Logic
            """CREATE TABLE IF NOT EXISTS forward_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_chat_id TEXT,
                media_type TEXT,
                file_id TEXT,
                caption TEXT,
                has_spoiler INTEGER DEFAULT 0,
                file_unique_id TEXT,
                media_group_id TEXT,
                created_at INTEGER,
                retry_count INTEGER DEFAULT 0,
                priority INTEGER DEFAULT 0,
                source_chat_id TEXT,
                source_msg_id TEXT,
                status INTEGER DEFAULT 0, -- 0: waiting, 1: processing
                updated_at INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS forward_log (
                source_chat_id TEXT,
                source_msg_id TEXT,
                target_chat_id TEXT,
                target_msg_id TEXT,
                created_at INTEGER,
                PRIMARY KEY (source_chat_id, source_msg_id, target_chat_id)
            )""",
            """CREATE TABLE IF NOT EXISTS dead_letter_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_chat_id TEXT,
                media_type TEXT,
                file_id TEXT,
                caption TEXT,
                has_spoiler INTEGER DEFAULT 0,
                file_unique_id TEXT,
                media_group_id TEXT,
                failed_at INTEGER,
                reason TEXT,
                source_chat_id TEXT,
                source_msg_id TEXT
            )""",
            # Configuration Tables
            """CREATE TABLE IF NOT EXISTS forward_map (
                source_chat_id TEXT, 
                target_chat_id TEXT,
                PRIMARY KEY (source_chat_id, target_chat_id)
            )""",
            """CREATE TABLE IF NOT EXISTS rules (
                chat_id TEXT, 
                rule TEXT,
                PRIMARY KEY (chat_id, rule)
            )""",
            """CREATE TABLE IF NOT EXISTS keywords (
                chat_id TEXT, 
                word TEXT, 
                is_regex INTEGER DEFAULT 0,
                PRIMARY KEY (chat_id, word)
            )""",
            """CREATE TABLE IF NOT EXISTS replacements (
                chat_id TEXT, 
                old_word TEXT, 
                new_word TEXT,
                PRIMARY KEY (chat_id, old_word)
            )""",
            """CREATE TABLE IF NOT EXISTS footers (
                chat_id TEXT PRIMARY KEY, 
                text TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS chat_locks (
                chat_id TEXT PRIMARY KEY, 
                is_locked INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS user_whitelist (
                chat_id TEXT, 
                user_id TEXT,
                PRIMARY KEY (chat_id, user_id)
            )""",
            """CREATE TABLE IF NOT EXISTS triggers (
                chat_id TEXT, 
                trigger_word TEXT, 
                response_text TEXT,
                PRIMARY KEY (chat_id, trigger_word)
            )""",
            """CREATE TABLE IF NOT EXISTS caption_templates (
                chat_id TEXT PRIMARY KEY, 
                template TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS media_filters (
                chat_id TEXT PRIMARY KEY, 
                allowed_types TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS quiet_settings (
                chat_id TEXT PRIMARY KEY, 
                mode TEXT DEFAULT 'off'
            )""",
            """CREATE TABLE IF NOT EXISTS vote_settings (
                chat_id TEXT PRIMARY KEY, 
                is_enabled INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS votes (
                chat_id TEXT, 
                message_id TEXT, 
                user_id TEXT, 
                vote_type TEXT,
                PRIMARY KEY (chat_id, message_id, user_id)
            )""",
            """CREATE TABLE IF NOT EXISTS log_settings (
                chat_id TEXT PRIMARY KEY, 
                log_channel TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS log_filters (
                chat_id TEXT PRIMARY KEY, 
                categories TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS forward_settings (
                min_delay INTEGER DEFAULT 10,
                max_delay INTEGER DEFAULT 60
            )""",
            """CREATE TABLE IF NOT EXISTS global_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )""",
            # Indexes
            "CREATE INDEX IF NOT EXISTS idx_seen_chat ON seen(chat_id)",
            "CREATE INDEX IF NOT EXISTS idx_fqueue_status ON forward_queue(status, updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_fqueue_priority ON forward_queue(priority DESC, id ASC)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_fqueue_dedup ON forward_queue(target_chat_id, file_unique_id, IFNULL(media_group_id, ''))",
        ]

        db = await self.get_db()
        for sql in schemas:
            try:
                await db.execute(sql)
            except Exception as e:
                # Handle cases where column might already exist or table mismatch
                if "already exists" in str(e).lower():
                    continue
                logger.warning(f"⚠️ Schema migration notice: {e}")

        # Incremental Migration: Add created_at if missing
        # This is a simple way to add columns to existing tables without complex migration frameworks
        tables_to_patch = [("forward_seen", "created_at", "INTEGER"), ("forward_log", "created_at", "INTEGER")]
        for table, col, col_type in tables_to_patch:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                logger.info(f"✨ Patched table {table} with column {col}")
            except Exception:
                pass  # Column already exists

        await db.commit()
        logger.info("🛠 Database schema verified/initialized.")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def is_alive(self) -> bool:
        if self._conn is None:
            return False
        try:
            await self._conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def execute(
        self, sql: str, args: tuple = (), fetchone: bool = False, fetchall: bool = False, commit: bool = False
    ) -> Any:
        sql_u = sql.strip().upper()
        is_write = any(
            sql_u.startswith(k) for k in ["INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER", "VACUUM"]
        )
        lock = self._write_lock if (is_write or commit) else contextlib.nullcontext()
        async with lock:
            db = await self.get_db()
            try:
                async with db.execute(sql, args) as cursor:
                    if commit or is_write:
                        await db.commit()
                    if fetchone:
                        return await cursor.fetchone()
                    if fetchall:
                        return await cursor.fetchall()
                    return cursor.rowcount
            except Exception as e:
                logger.error(f"❌ SQL Error: {sql} | {e}")
                if commit or is_write:
                    await db.rollback()
                raise

    async def execute_many(self, stmts: List[Tuple[str, tuple]]):
        async with self._write_lock:
            db = await self.get_db()
            try:
                async with db.cursor() as cursor:
                    for s, a in stmts:
                        await cursor.execute(s, a)
                await db.commit()
            except Exception:
                await db.rollback()
                raise


db_manager = DatabaseManager()
