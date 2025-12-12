# db.py
import aiosqlite
import asyncio
import time
import logging
from config import DB_FILE

# 全局数据库连接对象
_db_conn: aiosqlite.Connection = None
# 异步锁
db_lock = asyncio.Lock()


async def init_db_connection():
    """初始化全局数据库连接"""
    global _db_conn
    if _db_conn is None:
        _db_conn = await aiosqlite.connect(DB_FILE)
        # 开启 WAL 模式提高并发性能
        await _db_conn.execute("PRAGMA journal_mode=WAL;")
        await _db_conn.commit()
        logging.info("🔌 数据库连接已建立 (Persistent)")


async def close_db_connection():
    """关闭全局数据库连接"""
    global _db_conn
    if _db_conn:
        await _db_conn.close()
        _db_conn = None
        logging.info("🔌 数据库连接已关闭")


async def get_db() -> aiosqlite.Connection:
    """获取当前连接，如果未初始化则自动初始化"""
    if _db_conn is None:
        await init_db_connection()
    return _db_conn


async def init_db():
    """初始化表结构"""
    async with db_lock:
        db = await get_db()
        await db.execute(
            "CREATE TABLE IF NOT EXISTS seen (chat_id TEXT, file_unique_id TEXT, created_at INTEGER DEFAULT 0, PRIMARY KEY (chat_id, file_unique_id))")
        await db.execute("CREATE TABLE IF NOT EXISTS chats (chat_id TEXT PRIMARY KEY, title TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS keywords (chat_id TEXT, word TEXT, is_regex INTEGER DEFAULT 0)")
        await db.execute("CREATE TABLE IF NOT EXISTS locked (chat_id TEXT PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS stats (chat_id TEXT PRIMARY KEY, count INTEGER)")
        await db.execute("CREATE TABLE IF NOT EXISTS rules (chat_id TEXT, rule TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS admins (user_id TEXT PRIMARY KEY)")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS forward_map (source_chat_id TEXT, target_chat_id TEXT, PRIMARY KEY (source_chat_id, target_chat_id))")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS forward_seen (chat_id TEXT, file_unique_id TEXT, PRIMARY KEY (chat_id, file_unique_id))")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS album_forwarded (source_chat_id TEXT, media_group_id TEXT, target_chat_id TEXT, PRIMARY KEY (source_chat_id, media_group_id, target_chat_id))")
        await db.execute("CREATE TABLE IF NOT EXISTS footers (chat_id TEXT PRIMARY KEY, text TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS replacements (chat_id TEXT, old_word TEXT, new_word TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS user_whitelist (chat_id TEXT, user_id TEXT, PRIMARY KEY (chat_id, user_id))")
        await db.execute("CREATE TABLE IF NOT EXISTS quiet_mode (chat_id TEXT PRIMARY KEY, mode TEXT)")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS votes (chat_id TEXT, message_id TEXT, user_id TEXT, vote_type TEXT, PRIMARY KEY (chat_id, message_id, user_id))")
        await db.execute("CREATE TABLE IF NOT EXISTS vote_settings (chat_id TEXT PRIMARY KEY, is_enabled INTEGER)")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS triggers (chat_id TEXT, keyword TEXT, reply_text TEXT, PRIMARY KEY (chat_id, keyword))")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS forward_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT, target_chat_id TEXT, media_type TEXT, file_id TEXT, 
                caption TEXT, has_spoiler INTEGER DEFAULT 0, file_unique_id TEXT, media_group_id TEXT, created_at INTEGER
            )
        """)
        try:
            await db.execute("ALTER TABLE seen ADD COLUMN created_at INTEGER DEFAULT 0")
        except Exception:
            pass
        await db.commit()


async def execute_sql(sql: str, args: tuple = (), fetchone=False, fetchall=False, commit=False):
    """
    通用执行函数，复用全局连接
    [修复] 使用 context manager 自动关闭 cursor，防止资源泄漏
    """
    async with db_lock:
        db = await get_db()
        async with db.execute(sql, args) as cursor:
            if commit:
                await db.commit()

            if fetchone:
                return await cursor.fetchone()
            if fetchall:
                return await cursor.fetchall()
            return None


# --- 业务逻辑 ---
async def clean_expired_data(days: int = 365) -> int:
    expire_time = int(time.time()) - (days * 86400)
    async with db_lock:
        db = await get_db()
        async with db.execute("DELETE FROM seen WHERE created_at > 0 AND created_at < ?", (expire_time,)) as cursor:
            await db.commit()
            return cursor.rowcount


async def vacuum_db():
    async with db_lock:
        db = await get_db()
        await db.execute("VACUUM")


async def delete_chat_data(chat_id: str):
    tables = ["chats", "rules", "keywords", "locked", "stats", "footers", "replacements",
              "seen", "forward_seen", "user_whitelist", "quiet_mode", "votes", "vote_settings", "triggers"]
    async with db_lock:
        db = await get_db()
        for t in tables:
            await db.execute(f"DELETE FROM {t} WHERE chat_id=?", (chat_id,))
        await db.execute("DELETE FROM forward_map WHERE source_chat_id=? OR target_chat_id=?", (chat_id, chat_id))
        await db.execute("DELETE FROM album_forwarded WHERE source_chat_id=? OR target_chat_id=?", (chat_id, chat_id))
        await db.execute("DELETE FROM forward_queue WHERE target_chat_id=?", (chat_id,))
        await db.commit()


# --- CRUD 操作 ---
async def add_seen(chat_id, fid):
    try:
        await execute_sql("INSERT INTO seen (chat_id, file_unique_id, created_at) VALUES (?, ?, ?)",
                          (chat_id, fid, int(time.time())), commit=True)
    except:
        pass


async def has_seen(chat_id, fid) -> bool: return await execute_sql(
    "SELECT 1 FROM seen WHERE chat_id=? AND file_unique_id=?", (chat_id, fid), fetchone=True) is not None


async def save_chat(chat_id, title): await execute_sql("INSERT OR REPLACE INTO chats (chat_id, title) VALUES (?, ?)",
                                                       (chat_id, title), commit=True)


async def inc_stat(chat_id): await execute_sql(
    "INSERT INTO stats (chat_id, count) VALUES (?, 1) ON CONFLICT(chat_id) DO UPDATE SET count=count+1", (chat_id,),
    commit=True)


async def get_stats(): return await execute_sql("SELECT chat_id, count FROM stats ORDER BY count DESC", fetchall=True)


async def get_all_chat_ids(): return [r[0] for r in await execute_sql("SELECT chat_id FROM chats", fetchall=True)]


async def get_rules(cid): return [r[0] for r in
                                  await execute_sql("SELECT rule FROM rules WHERE chat_id=?", (cid,), fetchall=True)]


async def add_rule(cid, r): await execute_sql("INSERT INTO rules (chat_id, rule) VALUES (?, ?)", (cid, r), commit=True)


async def delete_rule(cid, r): await execute_sql("DELETE FROM rules WHERE chat_id=? AND rule=?", (cid, r), commit=True)


async def clear_rules(cid): await execute_sql("DELETE FROM rules WHERE chat_id=?", (cid,), commit=True)


async def get_keywords(cid): return [(w, bool(r)) for w, r in
                                     await execute_sql("SELECT word, is_regex FROM keywords WHERE chat_id=?", (cid,),
                                                       fetchall=True)]


async def add_keyword(cid, w, r=False): await execute_sql(
    "INSERT INTO keywords (chat_id, word, is_regex) VALUES (?, ?, ?)", (cid, w, 1 if r else 0), commit=True)


async def delete_keyword(cid, w): await execute_sql("DELETE FROM keywords WHERE chat_id=? AND word=?", (cid, w),
                                                    commit=True)


async def enqueue_forward(tid, mt, fid, cap, sp, fuid, mgid=None): await execute_sql(
    "INSERT INTO forward_queue (target_chat_id, media_type, file_id, caption, has_spoiler, file_unique_id, media_group_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    (tid, mt, fid, cap, 1 if sp else 0, fuid, mgid, int(time.time())), commit=True)


async def peek_forward_queue(): return await execute_sql("SELECT * FROM forward_queue ORDER BY id ASC LIMIT 1",
                                                         fetchone=True)


async def pop_forward_single(rid): await execute_sql("DELETE FROM forward_queue WHERE id=?", (rid,), commit=True)


async def pop_forward_group(tid, mgid):
    rows = await execute_sql("SELECT * FROM forward_queue WHERE target_chat_id=? AND media_group_id=? ORDER BY id ASC",
                             (tid, mgid), fetchall=True)
    if rows: await execute_sql("DELETE FROM forward_queue WHERE target_chat_id=? AND media_group_id=?", (tid, mgid),
                               commit=True)
    return rows


async def get_delay_settings():
    r = await execute_sql("SELECT value FROM settings WHERE key='forward_delay'", fetchone=True)
    if r and r[0]:
        try:
            return int(r[0].split(',')[0]), int(r[0].split(',')[1])
        except:
            pass
    return (0, 0)


async def set_delay_settings(min_s, max_s): await execute_sql(
    "INSERT OR REPLACE INTO settings (key, value) VALUES ('forward_delay', ?)", (f"{min_s},{max_s}",), commit=True)


async def is_locked(cid): return await execute_sql("SELECT 1 FROM locked WHERE chat_id=?", (cid,),
                                                   fetchone=True) is not None


async def lock_chat(cid): await execute_sql("INSERT OR IGNORE INTO locked (chat_id) VALUES (?)", (cid,), commit=True)


async def unlock_chat(cid): await execute_sql("DELETE FROM locked WHERE chat_id=?", (cid,), commit=True)


async def list_admins(): return [r[0] for r in await execute_sql("SELECT user_id FROM admins", fetchall=True)]


async def add_admin(uid): await execute_sql("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (uid,), commit=True)


async def delete_admin(uid): await execute_sql("DELETE FROM admins WHERE user_id=?", (uid,), commit=True)


async def get_forward_targets(src): return [r[0] for r in await execute_sql(
    "SELECT target_chat_id FROM forward_map WHERE source_chat_id=?", (src,), fetchall=True)]


async def add_forward(src, tgt): await execute_sql(
    "INSERT OR IGNORE INTO forward_map (source_chat_id, target_chat_id) VALUES (?, ?)", (src, tgt), commit=True)


async def del_forward(src, tgt): await execute_sql(
    "DELETE FROM forward_map WHERE source_chat_id=? AND target_chat_id=?", (src, tgt), commit=True)


async def list_forward(src): return await get_forward_targets(src)


async def add_forward_seen(cid, fid):
    try:
        await execute_sql("INSERT INTO forward_seen (chat_id, file_unique_id) VALUES (?, ?)", (cid, fid), commit=True)
    except:
        pass


async def has_forward_seen(cid, fid): return await execute_sql(
    "SELECT 1 FROM forward_seen WHERE chat_id=? AND file_unique_id=?", (cid, fid), fetchone=True) is not None


async def has_album_forwarded(s, g, t): return await execute_sql(
    "SELECT 1 FROM album_forwarded WHERE source_chat_id=? AND media_group_id=? AND target_chat_id=?", (s, g, t),
    fetchone=True) is not None


async def mark_album_forwarded(s, g, t):
    try:
        await execute_sql(
            "INSERT INTO album_forwarded (source_chat_id, media_group_id, target_chat_id) VALUES (?, ?, ?)", (s, g, t),
            commit=True)
    except:
        pass


async def is_voting_enabled(cid):
    r = await execute_sql("SELECT is_enabled FROM vote_settings WHERE chat_id=?", (cid,), fetchone=True)
    return r is not None and r[0] == 1


async def set_voting_enabled(cid, e): await execute_sql(
    "INSERT OR REPLACE INTO vote_settings (chat_id, is_enabled) VALUES (?, ?)", (cid, 1 if e else 0), commit=True)


async def get_vote_counts(cid, mid):
    rows = await execute_sql(
        "SELECT vote_type, COUNT(*) FROM votes WHERE chat_id=? AND message_id=? GROUP BY vote_type", (cid, mid),
        fetchall=True)
    c = {'up': 0, 'down': 0}
    for v, num in rows: c[v] = num
    return c['up'], c['down']


async def add_vote(cid, mid, uid, vt): await execute_sql(
    "INSERT OR REPLACE INTO votes (chat_id, message_id, user_id, vote_type) VALUES (?, ?, ?, ?)", (cid, mid, uid, vt),
    commit=True)


async def remove_vote(cid, mid, uid): await execute_sql(
    "DELETE FROM votes WHERE chat_id=? AND message_id=? AND user_id=?", (cid, mid, uid), commit=True)


async def get_user_vote(cid, mid, uid):
    r = await execute_sql("SELECT vote_type FROM votes WHERE chat_id=? AND message_id=? AND user_id=?", (cid, mid, uid),
                          fetchone=True)
    return r[0] if r else None


async def get_replacements(cid): return await execute_sql("SELECT old_word, new_word FROM replacements WHERE chat_id=?",
                                                          (cid,), fetchall=True)


async def add_replacement(cid, o, n): await execute_sql(
    "INSERT INTO replacements (chat_id, old_word, new_word) VALUES (?, ?, ?)", (cid, o, n), commit=True)


async def delete_replacement(cid, o): await execute_sql("DELETE FROM replacements WHERE chat_id=? AND old_word=?",
                                                        (cid, o), commit=True)


async def get_footer(cid):
    r = await execute_sql("SELECT text FROM footers WHERE chat_id=?", (cid,), fetchone=True)
    return r[0] if r else None


async def set_footer(cid, t): await execute_sql("INSERT OR REPLACE INTO footers (chat_id, text) VALUES (?, ?)",
                                                (cid, t), commit=True)


async def delete_footer(cid): await execute_sql("DELETE FROM footers WHERE chat_id=?", (cid,), commit=True)


async def get_chat_whitelist(cid): return [r[0] for r in
                                           await execute_sql("SELECT user_id FROM user_whitelist WHERE chat_id=?",
                                                             (cid,), fetchall=True)]


async def is_user_whitelisted(cid, uid): return await execute_sql(
    "SELECT 1 FROM user_whitelist WHERE chat_id=? AND user_id=?", (cid, uid), fetchone=True) is not None


async def add_user_whitelist(cid, uid): await execute_sql(
    "INSERT OR IGNORE INTO user_whitelist (chat_id, user_id) VALUES (?, ?)", (cid, uid), commit=True)


async def del_user_whitelist(cid, uid): await execute_sql("DELETE FROM user_whitelist WHERE chat_id=? AND user_id=?",
                                                          (cid, uid), commit=True)


async def get_quiet_mode(cid):
    r = await execute_sql("SELECT mode FROM quiet_mode WHERE chat_id=?", (cid,), fetchone=True)
    return r[0] if r else "off"


async def set_quiet_mode(cid, m): await execute_sql("INSERT OR REPLACE INTO quiet_mode (chat_id, mode) VALUES (?, ?)",
                                                    (cid, m), commit=True)


async def add_trigger(cid, kw, rt): await execute_sql(
    "INSERT OR REPLACE INTO triggers (chat_id, keyword, reply_text) VALUES (?, ?, ?)", (cid, kw, rt), commit=True)


async def del_trigger(cid, kw): await execute_sql("DELETE FROM triggers WHERE chat_id=? AND keyword=?", (cid, kw),
                                                  commit=True)


async def get_triggers(cid):
    rows = await execute_sql("SELECT keyword, reply_text FROM triggers WHERE chat_id=?", (cid,), fetchall=True)
    return {r[0]: r[1] for r in rows}


async def get_log_channel():
    r = await execute_sql("SELECT value FROM settings WHERE key='log_channel'", fetchone=True)
    return r[0] if r else None


async def set_log_channel(cid): await execute_sql(
    "INSERT OR REPLACE INTO settings (key, value) VALUES ('log_channel', ?)", (cid,), commit=True)


async def get_log_filter():
    r = await execute_sql("SELECT value FROM settings WHERE key='log_filter'", fetchone=True)
    return r[0].split(',') if r and r[0] else ['clean', 'duplicate', 'forward', 'error', 'system']


async def set_log_filter(v): await execute_sql("INSERT OR REPLACE INTO settings (key, value) VALUES ('log_filter', ?)",
                                               (",".join(v),), commit=True)


async def get_forward_queue_counts():
    """获取转发队列统计"""
    sql = """
        SELECT f.target_chat_id, c.title, COUNT(*) 
        FROM forward_queue f 
        LEFT JOIN chats c ON f.target_chat_id = c.chat_id 
        GROUP BY f.target_chat_id
        ORDER BY COUNT(*) DESC
    """
    return await execute_sql(sql, fetchall=True)


# [新增] 暂停/恢复状态管理
async def is_forward_paused():
    r = await execute_sql("SELECT value FROM settings WHERE key='forward_paused'", fetchone=True)
    return r is not None and r[0] == '1'


async def set_forward_paused(paused: bool):
    val = '1' if paused else '0'
    await execute_sql("INSERT OR REPLACE INTO settings (key, value) VALUES ('forward_paused', ?)", (val,), commit=True)