import sqlite3
import time
import threading
from functools import lru_cache
from config import DB_FILE

# 线程锁，防止 SQLite 并发写入报错
db_lock = threading.Lock()

def init_db():
    """初始化数据库表结构"""
    tables = [
        "CREATE TABLE IF NOT EXISTS seen (chat_id TEXT, file_unique_id TEXT, created_at INTEGER DEFAULT 0, PRIMARY KEY (chat_id, file_unique_id))",
        "CREATE TABLE IF NOT EXISTS chats (chat_id TEXT PRIMARY KEY, title TEXT)",
        "CREATE TABLE IF NOT EXISTS keywords (chat_id TEXT, word TEXT, is_regex INTEGER DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS locked (chat_id TEXT PRIMARY KEY)",
        "CREATE TABLE IF NOT EXISTS stats (chat_id TEXT PRIMARY KEY, count INTEGER)",
        "CREATE TABLE IF NOT EXISTS rules (chat_id TEXT, rule TEXT)",
        "CREATE TABLE IF NOT EXISTS admins (user_id TEXT PRIMARY KEY)",
        "CREATE TABLE IF NOT EXISTS forward_map (source_chat_id TEXT, target_chat_id TEXT, PRIMARY KEY (source_chat_id, target_chat_id))",
        "CREATE TABLE IF NOT EXISTS forward_seen (chat_id TEXT, file_unique_id TEXT, PRIMARY KEY (chat_id, file_unique_id))",
        "CREATE TABLE IF NOT EXISTS album_forwarded (source_chat_id TEXT, media_group_id TEXT, target_chat_id TEXT, PRIMARY KEY (source_chat_id, media_group_id, target_chat_id))",
        "CREATE TABLE IF NOT EXISTS footers (chat_id TEXT PRIMARY KEY, text TEXT)",
        "CREATE TABLE IF NOT EXISTS replacements (chat_id TEXT, old_word TEXT, new_word TEXT)",
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)",
        "CREATE TABLE IF NOT EXISTS user_whitelist (chat_id TEXT, user_id TEXT, PRIMARY KEY (chat_id, user_id))",
        "CREATE TABLE IF NOT EXISTS quiet_mode (chat_id TEXT PRIMARY KEY, mode TEXT)",
        "CREATE TABLE IF NOT EXISTS votes (chat_id TEXT, message_id TEXT, user_id TEXT, vote_type TEXT, PRIMARY KEY (chat_id, message_id, user_id))",
        "CREATE TABLE IF NOT EXISTS vote_settings (chat_id TEXT PRIMARY KEY, is_enabled INTEGER)",
        "CREATE TABLE IF NOT EXISTS triggers (chat_id TEXT, keyword TEXT, reply_text TEXT, PRIMARY KEY (chat_id, keyword))",
        """CREATE TABLE IF NOT EXISTS forward_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT, target_chat_id TEXT, media_type TEXT, file_id TEXT, 
            caption TEXT, has_spoiler INTEGER DEFAULT 0, file_unique_id TEXT, media_group_id TEXT, created_at INTEGER
        )"""
    ]
    with db_lock:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            for sql in tables:
                c.execute(sql)
            # 补丁：检查 seen 表是否需要加字段 (向下兼容)
            try:
                c.execute("ALTER TABLE seen ADD COLUMN created_at INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            conn.commit()

# --- 通用数据库操作封装 ---

def execute_sql(sql: str, args: tuple = (), fetchone=False, fetchall=False, commit=False):
    """通用的 SQL 执行函数"""
    with db_lock:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute(sql, args)
            if commit:
                conn.commit()
            if fetchone:
                return c.fetchone()
            if fetchall:
                return c.fetchall()
            return None

# --- 维护类 ---

def clean_expired_data(days: int = 365) -> int:
    expire_time = int(time.time()) - (days * 86400)
    with db_lock:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM seen WHERE created_at > 0 AND created_at < ?", (expire_time,))
            deleted = c.rowcount
            conn.commit()
    return deleted

def vacuum_db():
    execute_sql("VACUUM")

def delete_chat_data(chat_id: str):
    tables = ["chats", "rules", "keywords", "locked", "stats", "footers", "replacements",
              "seen", "forward_seen", "user_whitelist", "quiet_mode", "votes", "vote_settings", "triggers"]
    with db_lock:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            for t in tables:
                c.execute(f"DELETE FROM {t} WHERE chat_id=?", (chat_id,))
            c.execute("DELETE FROM forward_map WHERE source_chat_id=? OR target_chat_id=?", (chat_id, chat_id))
            c.execute("DELETE FROM album_forwarded WHERE source_chat_id=? OR target_chat_id=?", (chat_id, chat_id))
            c.execute("DELETE FROM forward_queue WHERE target_chat_id=?", (chat_id,))
            conn.commit()
    # 清除缓存
    get_rules.cache_clear()
    get_keywords.cache_clear()
    get_replacements.cache_clear()

# --- 业务逻辑 (精简版) ---

def add_seen(chat_id, fid):
    try:
        execute_sql("INSERT INTO seen (chat_id, file_unique_id, created_at) VALUES (?, ?, ?)", 
                    (chat_id, fid, int(time.time())), commit=True)
    except sqlite3.IntegrityError:
        pass

def has_seen(chat_id, fid) -> bool:
    return execute_sql("SELECT 1 FROM seen WHERE chat_id=? AND file_unique_id=?", (chat_id, fid), fetchone=True) is not None

def save_chat(chat_id, title):
    execute_sql("INSERT OR REPLACE INTO chats (chat_id, title) VALUES (?, ?)", (chat_id, title), commit=True)

def inc_stat(chat_id):
    execute_sql("INSERT INTO stats (chat_id, count) VALUES (?, 1) ON CONFLICT(chat_id) DO UPDATE SET count=count+1", (chat_id,), commit=True)

def get_stats():
    return execute_sql("SELECT chat_id, count FROM stats ORDER BY count DESC", fetchall=True)

def get_all_chat_ids():
    rows = execute_sql("SELECT chat_id FROM chats", fetchall=True)
    return [r[0] for r in rows]

# --- 缓存读取类 (Read Heavy) ---

@lru_cache(maxsize=128)
def get_rules(chat_id):
    rows = execute_sql("SELECT rule FROM rules WHERE chat_id=?", (chat_id,), fetchall=True)
    return [r[0] for r in rows]

def add_rule(chat_id, rule):
    execute_sql("INSERT INTO rules (chat_id, rule) VALUES (?, ?)", (chat_id, rule), commit=True)
    get_rules.cache_clear()

def clear_rules(chat_id):
    execute_sql("DELETE FROM rules WHERE chat_id=?", (chat_id,), commit=True)
    get_rules.cache_clear()

@lru_cache(maxsize=128)
def get_keywords(chat_id):
    rows = execute_sql("SELECT word, is_regex FROM keywords WHERE chat_id=?", (chat_id,), fetchall=True)
    return [(w, bool(r)) for w, r in rows]

def add_keyword(chat_id, word, is_regex=False):
    execute_sql("INSERT INTO keywords (chat_id, word, is_regex) VALUES (?, ?, ?)", 
                (chat_id, word, 1 if is_regex else 0), commit=True)
    get_keywords.cache_clear()

# --- 转发队列 ---

def enqueue_forward(target_id, media_type, file_id, caption, has_spoiler, file_unique_id, media_group_id=None):
    execute_sql("""
        INSERT INTO forward_queue 
        (target_chat_id, media_type, file_id, caption, has_spoiler, file_unique_id, media_group_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (target_id, media_type, file_id, caption, 1 if has_spoiler else 0, file_unique_id, media_group_id, int(time.time())), commit=True)

def peek_forward_queue():
    return execute_sql("SELECT * FROM forward_queue ORDER BY id ASC LIMIT 1", fetchone=True)

def pop_forward_single(row_id):
    execute_sql("DELETE FROM forward_queue WHERE id=?", (row_id,), commit=True)

def pop_forward_group(target_id, media_group_id):
    rows = execute_sql("SELECT * FROM forward_queue WHERE target_chat_id=? AND media_group_id=? ORDER BY id ASC", 
                       (target_id, media_group_id), fetchall=True)
    if rows:
        execute_sql("DELETE FROM forward_queue WHERE target_chat_id=? AND media_group_id=?", 
                    (target_id, media_group_id), commit=True)
    return rows

@lru_cache(maxsize=1)
def get_delay_settings():
    r = execute_sql("SELECT value FROM settings WHERE key='forward_delay'", fetchone=True)
    if r and r[0]:
        try:
            parts = r[0].split(',')
            return int(parts[0]), int(parts[1])
        except:
            pass
    return (0, 0)

def set_delay_settings(min_s, max_s):
    execute_sql("INSERT OR REPLACE INTO settings (key, value) VALUES ('forward_delay', ?)", (f"{min_s},{max_s}",), commit=True)
    get_delay_settings.cache_clear()

# --- 其他 Getter/Setter (省略部分重复逻辑以节省篇幅，参照上述模式封装) ---
# 注意：所有原有的 list_admins, add_admin, lock_chat 等都应用 execute_sql 封装
# 必须保留 config.py 中用到的所有 import 函数名
def is_locked(chat_id): return execute_sql("SELECT 1 FROM locked WHERE chat_id=?", (chat_id,), fetchone=True) is not None
def lock_chat(chat_id): execute_sql("INSERT OR IGNORE INTO locked (chat_id) VALUES (?)", (chat_id,), commit=True)
def unlock_chat(chat_id): execute_sql("DELETE FROM locked WHERE chat_id=?", (chat_id,), commit=True)
def list_admins(): return [r[0] for r in execute_sql("SELECT user_id FROM admins", fetchall=True)]
def add_admin(uid): execute_sql("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (uid,), commit=True)
def delete_admin(uid): execute_sql("DELETE FROM admins WHERE user_id=?", (uid,), commit=True)
def get_forward_targets(src): return [r[0] for r in execute_sql("SELECT target_chat_id FROM forward_map WHERE source_chat_id=?", (src,), fetchall=True)]
def add_forward(src, tgt): execute_sql("INSERT OR IGNORE INTO forward_map (source_chat_id, target_chat_id) VALUES (?, ?)", (src, tgt), commit=True)
def del_forward(src, tgt): execute_sql("DELETE FROM forward_map WHERE source_chat_id=? AND target_chat_id=?", (src, tgt), commit=True)

# 补全 media.py 需要的函数
def add_forward_seen(chat_id, fid):
    try: execute_sql("INSERT INTO forward_seen (chat_id, file_unique_id) VALUES (?, ?)", (chat_id, fid), commit=True)
    except: pass
def has_forward_seen(chat_id, fid): return execute_sql("SELECT 1 FROM forward_seen WHERE chat_id=? AND file_unique_id=?", (chat_id, fid), fetchone=True) is not None
def has_album_forwarded(s, g, t): return execute_sql("SELECT 1 FROM album_forwarded WHERE source_chat_id=? AND media_group_id=? AND target_chat_id=?", (s, g, t), fetchone=True) is not None
def mark_album_forwarded(s, g, t):
    try: execute_sql("INSERT INTO album_forwarded (source_chat_id, media_group_id, target_chat_id) VALUES (?, ?, ?)", (s, g, t), commit=True)
    except: pass

@lru_cache(maxsize=128)
def is_voting_enabled(chat_id):
    r = execute_sql("SELECT is_enabled FROM vote_settings WHERE chat_id=?", (chat_id,), fetchone=True)
    return r is not None and r[0] == 1
def set_voting_enabled(chat_id, enabled):
    execute_sql("INSERT OR REPLACE INTO vote_settings (chat_id, is_enabled) VALUES (?, ?)", (chat_id, 1 if enabled else 0), commit=True)
    is_voting_enabled.cache_clear()
def get_vote_counts(cid, mid):
    rows = execute_sql("SELECT vote_type, COUNT(*) FROM votes WHERE chat_id=? AND message_id=? GROUP BY vote_type", (cid, mid), fetchall=True)
    counts = {'up': 0, 'down': 0}
    for v, c in rows: counts[v] = c
    return counts['up'], counts['down']
def add_vote(cid, mid, uid, vtype): execute_sql("INSERT OR REPLACE INTO votes (chat_id, message_id, user_id, vote_type) VALUES (?, ?, ?, ?)", (cid, mid, uid, vtype), commit=True)
def remove_vote(cid, mid, uid): execute_sql("DELETE FROM votes WHERE chat_id=? AND message_id=? AND user_id=?", (cid, mid, uid), commit=True)
def get_user_vote(cid, mid, uid): 
    r = execute_sql("SELECT vote_type FROM votes WHERE chat_id=? AND message_id=? AND user_id=?", (cid, mid, uid), fetchone=True)
    return r[0] if r else None

# 补全 cleaner.py 需要的
@lru_cache(maxsize=128)
def get_replacements(chat_id): return execute_sql("SELECT old_word, new_word FROM replacements WHERE chat_id=?", (chat_id,), fetchall=True)
def add_replacement(chat_id, old, new): 
    execute_sql("INSERT INTO replacements (chat_id, old_word, new_word) VALUES (?, ?, ?)", (chat_id, old, new), commit=True)
    get_replacements.cache_clear()
def delete_replacement(chat_id, old):
    execute_sql("DELETE FROM replacements WHERE chat_id=? AND old_word=?", (chat_id, old), commit=True)
    get_replacements.cache_clear()
@lru_cache(maxsize=128)
def get_footer(chat_id):
    r = execute_sql("SELECT text FROM footers WHERE chat_id=?", (chat_id,), fetchone=True)
    return r[0] if r else None
def set_footer(chat_id, text): 
    execute_sql("INSERT OR REPLACE INTO footers (chat_id, text) VALUES (?, ?)", (chat_id, text), commit=True)
    get_footer.cache_clear()
def delete_footer(chat_id):
    execute_sql("DELETE FROM footers WHERE chat_id=?", (chat_id,), commit=True)
    get_footer.cache_clear()
@lru_cache(maxsize=128)
def get_chat_whitelist(chat_id): return [r[0] for r in execute_sql("SELECT user_id FROM user_whitelist WHERE chat_id=?", (chat_id,), fetchall=True)]
@lru_cache(maxsize=1024)
def is_user_whitelisted(chat_id, user_id): return execute_sql("SELECT 1 FROM user_whitelist WHERE chat_id=? AND user_id=?", (chat_id, user_id), fetchone=True) is not None
def add_user_whitelist(cid, uid): 
    execute_sql("INSERT OR IGNORE INTO user_whitelist (chat_id, user_id) VALUES (?, ?)", (cid, uid), commit=True)
    get_chat_whitelist.cache_clear(); is_user_whitelisted.cache_clear()
def del_user_whitelist(cid, uid):
    execute_sql("DELETE FROM user_whitelist WHERE chat_id=? AND user_id=?", (cid, uid), commit=True)
    get_chat_whitelist.cache_clear(); is_user_whitelisted.cache_clear()
@lru_cache(maxsize=128)
def get_quiet_mode(chat_id):
    r = execute_sql("SELECT mode FROM quiet_mode WHERE chat_id=?", (chat_id,), fetchone=True)
    return r[0] if r else "off"
def set_quiet_mode(cid, mode):
    execute_sql("INSERT OR REPLACE INTO quiet_mode (chat_id, mode) VALUES (?, ?)", (cid, mode), commit=True)
    get_quiet_mode.cache_clear()
# Triggers
def add_trigger(cid, kw, reply): 
    execute_sql("INSERT OR REPLACE INTO triggers (chat_id, keyword, reply_text) VALUES (?, ?, ?)", (cid, kw, reply), commit=True)
    get_triggers.cache_clear()
def del_trigger(cid, kw):
    execute_sql("DELETE FROM triggers WHERE chat_id=? AND keyword=?", (cid, kw), commit=True)
    get_triggers.cache_clear()
@lru_cache(maxsize=128)
def get_triggers(cid):
    rows = execute_sql("SELECT keyword, reply_text FROM triggers WHERE chat_id=?", (cid,), fetchall=True)
    return {r[0]: r[1] for r in rows}

# Log
def get_log_channel():
    r = execute_sql("SELECT value FROM settings WHERE key='log_channel'", fetchone=True)
    return r[0] if r else None
def set_log_channel(cid): execute_sql("INSERT OR REPLACE INTO settings (key, value) VALUES ('log_channel', ?)", (cid,), commit=True)
def get_log_filter():
    r = execute_sql("SELECT value FROM settings WHERE key='log_filter'", fetchone=True)
    return r[0].split(',') if r and r[0] else ['clean', 'duplicate', 'forward', 'error', 'system']
def set_log_filter(v): execute_sql("INSERT OR REPLACE INTO settings (key, value) VALUES ('log_filter', ?)", (",".join(v),), commit=True)