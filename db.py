import aiosqlite
import asyncio
import time
from config import DB_FILE

# 全局异步锁，防止高并发下的逻辑冲突
db_lock = asyncio.Lock()

async def init_db():
    async with db_lock:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS seen (chat_id TEXT, file_unique_id TEXT, created_at INTEGER DEFAULT 0, PRIMARY KEY (chat_id, file_unique_id))")
            await db.execute("CREATE TABLE IF NOT EXISTS chats (chat_id TEXT PRIMARY KEY, title TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS keywords (chat_id TEXT, word TEXT, is_regex INTEGER DEFAULT 0)")
            await db.execute("CREATE TABLE IF NOT EXISTS locked (chat_id TEXT PRIMARY KEY)")
            await db.execute("CREATE TABLE IF NOT EXISTS stats (chat_id TEXT PRIMARY KEY, count INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS rules (chat_id TEXT, rule TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS admins (user_id TEXT PRIMARY KEY)")
            await db.execute("CREATE TABLE IF NOT EXISTS forward_map (source_chat_id TEXT, target_chat_id TEXT, PRIMARY KEY (source_chat_id, target_chat_id))")
            await db.execute("CREATE TABLE IF NOT EXISTS forward_seen (chat_id TEXT, file_unique_id TEXT, PRIMARY KEY (chat_id, file_unique_id))")
            await db.execute("CREATE TABLE IF NOT EXISTS album_forwarded (source_chat_id TEXT, media_group_id TEXT, target_chat_id TEXT, PRIMARY KEY (source_chat_id, media_group_id, target_chat_id))")
            await db.execute("CREATE TABLE IF NOT EXISTS footers (chat_id TEXT PRIMARY KEY, text TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS replacements (chat_id TEXT, old_word TEXT, new_word TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS user_whitelist (chat_id TEXT, user_id TEXT, PRIMARY KEY (chat_id, user_id))")
            await db.execute("CREATE TABLE IF NOT EXISTS quiet_mode (chat_id TEXT PRIMARY KEY, mode TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS votes (chat_id TEXT, message_id TEXT, user_id TEXT, vote_type TEXT, PRIMARY KEY (chat_id, message_id, user_id))")
            await db.execute("CREATE TABLE IF NOT EXISTS vote_settings (chat_id TEXT PRIMARY KEY, is_enabled INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS triggers (chat_id TEXT, keyword TEXT, reply_text TEXT, PRIMARY KEY (chat_id, keyword))")
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
    async with db_lock:
        async with aiosqlite.connect(DB_FILE) as db:
            cursor = await db.execute(sql, args)
            if commit:
                await db.commit()
            res = None
            if fetchone:
                res = await cursor.fetchone()
            elif fetchall:
                res = await cursor.fetchall()
            await cursor.close()
            return res

# --- 维护 ---
async def clean_expired_data(days: int = 365) -> int:
    expire_time = int(time.time()) - (days * 86400)
    async with db_lock:
        async with aiosqlite.connect(DB_FILE) as db:
            cursor = await db.execute("DELETE FROM seen WHERE created_at > 0 AND created_at < ?", (expire_time,))
            await db.commit()
            return cursor.rowcount

async def vacuum_db():
    await execute_sql("VACUUM")

async def delete_chat_data(chat_id: str):
    tables = ["chats", "rules", "keywords", "locked", "stats", "footers", "replacements",
              "seen", "forward_seen", "user_whitelist", "quiet_mode", "votes", "vote_settings", "triggers"]
    async with db_lock:
        async with aiosqlite.connect(DB_FILE) as db:
            for t in tables:
                await db.execute(f"DELETE FROM {t} WHERE chat_id=?", (chat_id,))
            await db.execute("DELETE FROM forward_map WHERE source_chat_id=? OR target_chat_id=?", (chat_id, chat_id))
            await db.execute("DELETE FROM album_forwarded WHERE source_chat_id=? OR target_chat_id=?", (chat_id, chat_id))
            await db.execute("DELETE FROM forward_queue WHERE target_chat_id=?", (chat_id,))
            await db.commit()

# --- 业务逻辑 ---
async def add_seen(chat_id, fid):
    try: await execute_sql("INSERT INTO seen (chat_id, file_unique_id, created_at) VALUES (?, ?, ?)", (chat_id, fid, int(time.time())), commit=True)
    except: pass

async def has_seen(chat_id, fid) -> bool:
    return await execute_sql("SELECT 1 FROM seen WHERE chat_id=? AND file_unique_id=?", (chat_id, fid), fetchone=True) is not None

async def save_chat(chat_id, title):
    await execute_sql("INSERT OR REPLACE INTO chats (chat_id, title) VALUES (?, ?)", (chat_id, title), commit=True)

async def inc_stat(chat_id):
    await execute_sql("INSERT INTO stats (chat_id, count) VALUES (?, 1) ON CONFLICT(chat_id) DO UPDATE SET count=count+1", (chat_id,), commit=True)

async def get_stats():
    return await execute_sql("SELECT chat_id, count FROM stats ORDER BY count DESC", fetchall=True)

async def get_all_chat_ids():
    rows = await execute_sql("SELECT chat_id FROM chats", fetchall=True)
    return [r[0] for r in rows]

async def get_rules(chat_id):
    rows = await execute_sql("SELECT rule FROM rules WHERE chat_id=?", (chat_id,), fetchall=True)
    return [r[0] for r in rows]

async def add_rule(chat_id, rule):
    await execute_sql("INSERT INTO rules (chat_id, rule) VALUES (?, ?)", (chat_id, rule), commit=True)

async def delete_rule(chat_id, rule):
    await execute_sql("DELETE FROM rules WHERE chat_id=? AND rule=?", (chat_id, rule), commit=True)

async def clear_rules(chat_id):
    await execute_sql("DELETE FROM rules WHERE chat_id=?", (chat_id,), commit=True)

async def get_keywords(chat_id):
    rows = await execute_sql("SELECT word, is_regex FROM keywords WHERE chat_id=?", (chat_id,), fetchall=True)
    return [(w, bool(r)) for w, r in rows]

async def add_keyword(chat_id, word, is_regex=False):
    await execute_sql("INSERT INTO keywords (chat_id, word, is_regex) VALUES (?, ?, ?)", (chat_id, word, 1 if is_regex else 0), commit=True)

async def delete_keyword(chat_id, word):
    await execute_sql("DELETE FROM keywords WHERE chat_id=? AND word=?", (chat_id, word), commit=True)

# 转发队列
async def enqueue_forward(target_id, media_type, file_id, caption, has_spoiler, file_unique_id, media_group_id=None):
    await execute_sql("""
        INSERT INTO forward_queue 
        (target_chat_id, media_type, file_id, caption, has_spoiler, file_unique_id, media_group_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (target_id, media_type, file_id, caption, 1 if has_spoiler else 0, file_unique_id, media_group_id, int(time.time())), commit=True)

async def peek_forward_queue():
    return await execute_sql("SELECT * FROM forward_queue ORDER BY id ASC LIMIT 1", fetchone=True)

async def pop_forward_single(row_id):
    await execute_sql("DELETE FROM forward_queue WHERE id=?", (row_id,), commit=True)

async def pop_forward_group(target_id, media_group_id):
    rows = await execute_sql("SELECT * FROM forward_queue WHERE target_chat_id=? AND media_group_id=? ORDER BY id ASC", (target_id, media_group_id), fetchall=True)
    if rows:
        await execute_sql("DELETE FROM forward_queue WHERE target_chat_id=? AND media_group_id=?", (target_id, media_group_id), commit=True)
    return rows

async def get_delay_settings():
    r = await execute_sql("SELECT value FROM settings WHERE key='forward_delay'", fetchone=True)
    if r and r[0]:
        try:
            parts = r[0].split(',')
            return int(parts[0]), int(parts[1])
        except: pass
    return (0, 0)

async def set_delay_settings(min_s, max_s):
    await execute_sql("INSERT OR REPLACE INTO settings (key, value) VALUES ('forward_delay', ?)", (f"{min_s},{max_s}",), commit=True)

# 其他辅助
async def is_locked(chat_id): return await execute_sql("SELECT 1 FROM locked WHERE chat_id=?", (chat_id,), fetchone=True) is not None
async def lock_chat(chat_id): await execute_sql("INSERT OR IGNORE INTO locked (chat_id) VALUES (?)", (chat_id,), commit=True)
async def unlock_chat(chat_id): await execute_sql("DELETE FROM locked WHERE chat_id=?", (chat_id,), commit=True)
async def list_admins(): return [r[0] for r in await execute_sql("SELECT user_id FROM admins", fetchall=True)]
async def add_admin(uid): await execute_sql("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (uid,), commit=True)
async def delete_admin(uid): await execute_sql("DELETE FROM admins WHERE user_id=?", (uid,), commit=True)
async def get_forward_targets(src): return [r[0] for r in await execute_sql("SELECT target_chat_id FROM forward_map WHERE source_chat_id=?", (src,), fetchall=True)]
async def add_forward(src, tgt): await execute_sql("INSERT OR IGNORE INTO forward_map (source_chat_id, target_chat_id) VALUES (?, ?)", (src, tgt), commit=True)
async def del_forward(src, tgt): await execute_sql("DELETE FROM forward_map WHERE source_chat_id=? AND target_chat_id=?", (src, tgt), commit=True)
async def list_forward(src): return await get_forward_targets(src)

async def add_forward_seen(chat_id, fid):
    try: await execute_sql("INSERT INTO forward_seen (chat_id, file_unique_id) VALUES (?, ?)", (chat_id, fid), commit=True)
    except: pass
async def has_forward_seen(chat_id, fid): return await execute_sql("SELECT 1 FROM forward_seen WHERE chat_id=? AND file_unique_id=?", (chat_id, fid), fetchone=True) is not None
async def has_album_forwarded(s, g, t): return await execute_sql("SELECT 1 FROM album_forwarded WHERE source_chat_id=? AND media_group_id=? AND target_chat_id=?", (s, g, t), fetchone=True) is not None
async def mark_album_forwarded(s, g, t):
    try: await execute_sql("INSERT INTO album_forwarded (source_chat_id, media_group_id, target_chat_id) VALUES (?, ?, ?)", (s, g, t), commit=True)
    except: pass

async def is_voting_enabled(chat_id):
    r = await execute_sql("SELECT is_enabled FROM vote_settings WHERE chat_id=?", (chat_id,), fetchone=True)
    return r is not None and r[0] == 1
async def set_voting_enabled(chat_id, enabled):
    await execute_sql("INSERT OR REPLACE INTO vote_settings (chat_id, is_enabled) VALUES (?, ?)", (chat_id, 1 if enabled else 0), commit=True)

async def get_vote_counts(cid, mid):
    rows = await execute_sql("SELECT vote_type, COUNT(*) FROM votes WHERE chat_id=? AND message_id=? GROUP BY vote_type", (cid, mid), fetchall=True)
    counts = {'up': 0, 'down': 0}
    for v, c in rows: counts[v] = c
    return counts['up'], counts['down']
async def add_vote(cid, mid, uid, vtype): await execute_sql("INSERT OR REPLACE INTO votes (chat_id, message_id, user_id, vote_type) VALUES (?, ?, ?, ?)", (cid, mid, uid, vtype), commit=True)
async def remove_vote(cid, mid, uid): await execute_sql("DELETE FROM votes WHERE chat_id=? AND message_id=? AND user_id=?", (cid, mid, uid), commit=True)
async def get_user_vote(cid, mid, uid):
    r = await execute_sql("SELECT vote_type FROM votes WHERE chat_id=? AND message_id=? AND user_id=?", (cid, mid, uid), fetchone=True)
    return r[0] if r else None

async def get_replacements(chat_id): return await execute_sql("SELECT old_word, new_word FROM replacements WHERE chat_id=?", (chat_id,), fetchall=True)
async def add_replacement(chat_id, old, new): await execute_sql("INSERT INTO replacements (chat_id, old_word, new_word) VALUES (?, ?, ?)", (chat_id, old, new), commit=True)
async def delete_replacement(chat_id, old): await execute_sql("DELETE FROM replacements WHERE chat_id=? AND old_word=?", (chat_id, old), commit=True)

async def get_footer(chat_id):
    r = await execute_sql("SELECT text FROM footers WHERE chat_id=?", (chat_id,), fetchone=True)
    return r[0] if r else None
async def set_footer(chat_id, text): await execute_sql("INSERT OR REPLACE INTO footers (chat_id, text) VALUES (?, ?)", (chat_id, text), commit=True)
async def delete_footer(chat_id): await execute_sql("DELETE FROM footers WHERE chat_id=?", (chat_id,), commit=True)

async def get_chat_whitelist(chat_id): return [r[0] for r in await execute_sql("SELECT user_id FROM user_whitelist WHERE chat_id=?", (chat_id,), fetchall=True)]
async def is_user_whitelisted(chat_id, user_id): return await execute_sql("SELECT 1 FROM user_whitelist WHERE chat_id=? AND user_id=?", (chat_id, user_id), fetchone=True) is not None
async def add_user_whitelist(cid, uid): await execute_sql("INSERT OR IGNORE INTO user_whitelist (chat_id, user_id) VALUES (?, ?)", (cid, uid), commit=True)
async def del_user_whitelist(cid, uid): await execute_sql("DELETE FROM user_whitelist WHERE chat_id=? AND user_id=?", (cid, uid), commit=True)

async def get_quiet_mode(chat_id):
    r = await execute_sql("SELECT mode FROM quiet_mode WHERE chat_id=?", (chat_id,), fetchone=True)
    return r[0] if r else "off"
async def set_quiet_mode(cid, mode): await execute_sql("INSERT OR REPLACE INTO quiet_mode (chat_id, mode) VALUES (?, ?)", (cid, mode), commit=True)

async def add_trigger(cid, kw, reply): await execute_sql("INSERT OR REPLACE INTO triggers (chat_id, keyword, reply_text) VALUES (?, ?, ?)", (cid, kw, reply), commit=True)
async def del_trigger(cid, kw): await execute_sql("DELETE FROM triggers WHERE chat_id=? AND keyword=?", (cid, kw), commit=True)
async def get_triggers(cid):
    rows = await execute_sql("SELECT keyword, reply_text FROM triggers WHERE chat_id=?", (cid,), fetchall=True)
    return {r[0]: r[1] for r in rows}

async def get_log_channel():
    r = await execute_sql("SELECT value FROM settings WHERE key='log_channel'", fetchone=True)
    return r[0] if r else None
async def set_log_channel(cid): await execute_sql("INSERT OR REPLACE INTO settings (key, value) VALUES ('log_channel', ?)", (cid,), commit=True)
async def get_log_filter():
    r = await execute_sql("SELECT value FROM settings WHERE key='log_filter'", fetchone=True)
    return r[0].split(',') if r and r[0] else ['clean', 'duplicate', 'forward', 'error', 'system']
async def set_log_filter(v): await execute_sql("INSERT OR REPLACE INTO settings (key, value) VALUES ('log_filter', ?)", (",".join(v),), commit=True)