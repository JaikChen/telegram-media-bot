# db.py
import sqlite3
import time
from functools import lru_cache
from config import DB_FILE


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 1. 基础核心表 (带自动升级 created_at)
    c.execute("""
        CREATE TABLE IF NOT EXISTS seen (
            chat_id TEXT,
            file_unique_id TEXT,
            created_at INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, file_unique_id)
        )
    """)
    try:
        c.execute("ALTER TABLE seen ADD COLUMN created_at INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # 其他表结构
    c.execute("CREATE TABLE IF NOT EXISTS chats (chat_id TEXT PRIMARY KEY, title TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS keywords (chat_id TEXT, word TEXT, is_regex INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS locked (chat_id TEXT PRIMARY KEY)")
    c.execute("CREATE TABLE IF NOT EXISTS stats (chat_id TEXT PRIMARY KEY, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS rules (chat_id TEXT, rule TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS admins (user_id TEXT PRIMARY KEY)")

    c.execute(
        "CREATE TABLE IF NOT EXISTS forward_map (source_chat_id TEXT, target_chat_id TEXT, PRIMARY KEY (source_chat_id, target_chat_id))")
    c.execute(
        "CREATE TABLE IF NOT EXISTS forward_seen (chat_id TEXT, file_unique_id TEXT, PRIMARY KEY (chat_id, file_unique_id))")
    c.execute(
        "CREATE TABLE IF NOT EXISTS album_forwarded (source_chat_id TEXT, media_group_id TEXT, target_chat_id TEXT, PRIMARY KEY (source_chat_id, media_group_id, target_chat_id))")

    c.execute("CREATE TABLE IF NOT EXISTS footers (chat_id TEXT PRIMARY KEY, text TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS replacements (chat_id TEXT, old_word TEXT, new_word TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS user_whitelist (chat_id TEXT, user_id TEXT, PRIMARY KEY (chat_id, user_id))")
    c.execute("CREATE TABLE IF NOT EXISTS quiet_mode (chat_id TEXT PRIMARY KEY, mode TEXT)")

    c.execute(
        "CREATE TABLE IF NOT EXISTS votes (chat_id TEXT, message_id TEXT, user_id TEXT, vote_type TEXT, PRIMARY KEY (chat_id, message_id, user_id))")
    c.execute("CREATE TABLE IF NOT EXISTS vote_settings (chat_id TEXT PRIMARY KEY, is_enabled INTEGER)")

    conn.commit()
    conn.close()


# --- 维护 ---
def clean_expired_data(days: int = 3650) -> int:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    expire_time = int(time.time()) - (days * 86400)
    c.execute("DELETE FROM seen WHERE created_at > 0 AND created_at < ?", (expire_time,))
    deleted_count = c.rowcount
    conn.commit()
    conn.close()
    return deleted_count


def vacuum_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("VACUUM")
    conn.close()


def delete_chat_data(chat_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    tables = ["chats", "rules", "keywords", "locked", "stats", "footers", "replacements",
              "seen", "forward_seen", "user_whitelist", "quiet_mode", "votes", "vote_settings"]
    for t in tables:
        c.execute(f"DELETE FROM {t} WHERE chat_id=?", (chat_id,))
    c.execute("DELETE FROM forward_map WHERE source_chat_id=? OR target_chat_id=?", (chat_id, chat_id))
    c.execute("DELETE FROM album_forwarded WHERE source_chat_id=? OR target_chat_id=?", (chat_id, chat_id))
    conn.commit()
    conn.close()

    # 清除缓存
    get_rules.cache_clear()
    get_keywords.cache_clear()
    get_footer.cache_clear()
    get_replacements.cache_clear()
    get_chat_whitelist.cache_clear()
    is_user_whitelisted.cache_clear()
    get_quiet_mode.cache_clear()
    is_voting_enabled.cache_clear()


# --- 核心读写 ---
def add_seen(chat_id: str, fid: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO seen (chat_id, file_unique_id, created_at) VALUES (?, ?, ?)",
                  (chat_id, fid, int(time.time())))
    except sqlite3.IntegrityError:
        pass
    conn.commit();
    conn.close()


def has_seen(chat_id: str, fid: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM seen WHERE chat_id=? AND file_unique_id=?", (chat_id, fid))
    r = c.fetchone();
    conn.close()
    return r is not None


def add_forward_seen(chat_id: str, fid: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO forward_seen (chat_id, file_unique_id) VALUES (?, ?)", (chat_id, fid))
    except sqlite3.IntegrityError:
        pass
    conn.commit();
    conn.close()


def has_forward_seen(chat_id: str, fid: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM forward_seen WHERE chat_id=? AND file_unique_id=?", (chat_id, fid))
    r = c.fetchone();
    conn.close()
    return r is not None


def save_chat(chat_id: str, title: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO chats (chat_id, title) VALUES (?, ?)", (chat_id, title))
    conn.commit();
    conn.close()


def inc_stat(chat_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO stats (chat_id, count) VALUES (?, 1) ON CONFLICT(chat_id) DO UPDATE SET count=count+1",
              (chat_id,))
    conn.commit();
    conn.close()


def get_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT chat_id, count FROM stats ORDER BY count DESC")
    rows = c.fetchall();
    conn.close()
    return rows


# --- 规则与配置 (带缓存) ---
@lru_cache(maxsize=128)
def get_rules(chat_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT rule FROM rules WHERE chat_id=?", (chat_id,))
    rows = c.fetchall();
    conn.close()
    return [r[0] for r in rows]


def add_rule(chat_id: str, rule: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("INSERT INTO rules (chat_id, rule) VALUES (?, ?)", (chat_id, rule))
    conn.commit();
    conn.close();
    get_rules.cache_clear()


def delete_rule(chat_id: str, rule: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("DELETE FROM rules WHERE chat_id=? AND rule=?", (chat_id, rule))
    conn.commit();
    conn.close();
    get_rules.cache_clear()


def clear_rules(chat_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("DELETE FROM rules WHERE chat_id=?", (chat_id,))
    conn.commit();
    conn.close();
    get_rules.cache_clear()


@lru_cache(maxsize=128)
def get_keywords(chat_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT word, is_regex FROM keywords WHERE chat_id=?", (chat_id,))
    rows = c.fetchall();
    conn.close()
    return [(w, bool(r)) for w, r in rows]


def add_keyword(chat_id: str, word: str, is_regex: bool = False):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("INSERT INTO keywords (chat_id, word, is_regex) VALUES (?, ?, ?)", (chat_id, word, 1 if is_regex else 0))
    conn.commit();
    conn.close();
    get_keywords.cache_clear()


def delete_keyword(chat_id: str, word: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("DELETE FROM keywords WHERE chat_id=? AND word=?", (chat_id, word))
    conn.commit();
    conn.close();
    get_keywords.cache_clear()


@lru_cache(maxsize=128)
def get_footer(chat_id: str) -> str | None:
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT text FROM footers WHERE chat_id=?", (chat_id,))
    r = c.fetchone();
    conn.close()
    return r[0] if r else None


def set_footer(chat_id: str, text: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO footers (chat_id, text) VALUES (?, ?)", (chat_id, text))
    conn.commit();
    conn.close();
    get_footer.cache_clear()


def delete_footer(chat_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("DELETE FROM footers WHERE chat_id=?", (chat_id,))
    conn.commit();
    conn.close();
    get_footer.cache_clear()


@lru_cache(maxsize=128)
def get_replacements(chat_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT old_word, new_word FROM replacements WHERE chat_id=?", (chat_id,))
    rows = c.fetchall();
    conn.close()
    return rows


def add_replacement(chat_id: str, old: str, new: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("INSERT INTO replacements (chat_id, old_word, new_word) VALUES (?, ?, ?)", (chat_id, old, new))
    conn.commit();
    conn.close();
    get_replacements.cache_clear()


def delete_replacement(chat_id: str, old: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("DELETE FROM replacements WHERE chat_id=? AND old_word=?", (chat_id, old))
    conn.commit();
    conn.close();
    get_replacements.cache_clear()


# --- 锁定 ---
def lock_chat(chat_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO locked (chat_id) VALUES (?)", (chat_id,))
    conn.commit();
    conn.close()


def unlock_chat(chat_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("DELETE FROM locked WHERE chat_id=?", (chat_id,))
    conn.commit();
    conn.close()


def is_locked(chat_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT 1 FROM locked WHERE chat_id=?", (chat_id,))
    r = c.fetchone();
    conn.close()
    return r is not None


# --- 管理员 ---
def add_admin(user_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit();
    conn.close()


def delete_admin(user_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
    conn.commit();
    conn.close()


def list_admins():
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT user_id FROM admins")
    rows = c.fetchall();
    conn.close()
    return [r[0] for r in rows]


# --- 转发 ---
def add_forward(source, target):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    try:
        c.execute("INSERT INTO forward_map (source_chat_id, target_chat_id) VALUES (?, ?)", (source, target))
    except sqlite3.IntegrityError:
        pass
    conn.commit();
    conn.close()


def del_forward(source, target):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("DELETE FROM forward_map WHERE source_chat_id=? AND target_chat_id=?", (source, target))
    conn.commit();
    conn.close()


def list_forward(source):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT target_chat_id FROM forward_map WHERE source_chat_id=?", (source,))
    rows = c.fetchall();
    conn.close()
    return [r[0] for r in rows]


def get_forward_targets(source): return list_forward(source)


def has_album_forwarded(source, gid, target) -> bool:
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT 1 FROM album_forwarded WHERE source_chat_id=? AND media_group_id=? AND target_chat_id=?",
              (source, gid, target))
    r = c.fetchone();
    conn.close()
    return r is not None


def mark_album_forwarded(source, gid, target):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    try:
        c.execute("INSERT INTO album_forwarded (source_chat_id, media_group_id, target_chat_id) VALUES (?, ?, ?)",
                  (source, gid, target))
    except sqlite3.IntegrityError:
        pass
    conn.commit();
    conn.close()


# --- 日志 ---
@lru_cache(maxsize=1)
def get_log_channel() -> str | None:
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='log_channel'")
    r = c.fetchone();
    conn.close()
    return r[0] if r else None


def set_log_channel(chat_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('log_channel', ?)", (chat_id,))
    conn.commit();
    conn.close();
    get_log_channel.cache_clear()


# --- 白名单 ---
@lru_cache(maxsize=128)
def get_chat_whitelist(chat_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT user_id FROM user_whitelist WHERE chat_id=?", (chat_id,))
    rows = c.fetchall();
    conn.close()
    return [r[0] for r in rows]


@lru_cache(maxsize=1024)
def is_user_whitelisted(chat_id: str, user_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT 1 FROM user_whitelist WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    r = c.fetchone();
    conn.close()
    return r is not None


def add_user_whitelist(chat_id: str, user_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO user_whitelist (chat_id, user_id) VALUES (?, ?)", (chat_id, user_id))
    conn.commit();
    conn.close()
    get_chat_whitelist.cache_clear();
    is_user_whitelisted.cache_clear()


def del_user_whitelist(chat_id: str, user_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("DELETE FROM user_whitelist WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    conn.commit();
    conn.close()
    get_chat_whitelist.cache_clear();
    is_user_whitelisted.cache_clear()


# --- 静音模式 ---
@lru_cache(maxsize=128)
def get_quiet_mode(chat_id: str) -> str:
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT mode FROM quiet_mode WHERE chat_id=?", (chat_id,))
    r = c.fetchone();
    conn.close()
    return r[0] if r else "off"


def set_quiet_mode(chat_id: str, mode: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO quiet_mode (chat_id, mode) VALUES (?, ?)", (chat_id, mode))
    conn.commit();
    conn.close();
    get_quiet_mode.cache_clear()


# --- 投票 ---
@lru_cache(maxsize=128)
def is_voting_enabled(chat_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT is_enabled FROM vote_settings WHERE chat_id=?", (chat_id,))
    r = c.fetchone();
    conn.close()
    return r is not None and r[0] == 1


def set_voting_enabled(chat_id: str, enabled: bool):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO vote_settings (chat_id, is_enabled) VALUES (?, ?)",
              (chat_id, 1 if enabled else 0))
    conn.commit();
    conn.close();
    is_voting_enabled.cache_clear()


def get_vote_counts(chat_id: str, message_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT vote_type, COUNT(*) FROM votes WHERE chat_id=? AND message_id=? GROUP BY vote_type",
              (chat_id, message_id))
    rows = c.fetchall();
    conn.close()
    counts = {'up': 0, 'down': 0}
    for v, c in rows: counts[v] = c
    return counts['up'], counts['down']


def get_user_vote(chat_id: str, message_id: str, user_id: str):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT vote_type FROM votes WHERE chat_id=? AND message_id=? AND user_id=?",
              (chat_id, message_id, user_id))
    r = c.fetchone();
    conn.close()
    return r[0] if r else None


def add_vote(chat_id, message_id, user_id, vote_type):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO votes (chat_id, message_id, user_id, vote_type) VALUES (?, ?, ?, ?)",
              (chat_id, message_id, user_id, vote_type))
    conn.commit();
    conn.close()


def remove_vote(chat_id, message_id, user_id):
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("DELETE FROM votes WHERE chat_id=? AND message_id=? AND user_id=?", (chat_id, message_id, user_id))
    conn.commit();
    conn.close()