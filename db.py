# db.py
# 数据库操作：组合规则、关键词、管理员、统计等

import sqlite3
from config import DB_FILE

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS seen (source TEXT, file_unique_id TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS chats (chat_id TEXT PRIMARY KEY, title TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS keywords (chat_id TEXT, word TEXT, is_regex INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS locked (chat_id TEXT PRIMARY KEY)")
    c.execute("CREATE TABLE IF NOT EXISTS stats (chat_id TEXT PRIMARY KEY, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS rules (chat_id TEXT, rule TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS admins (user_id TEXT PRIMARY KEY)")
    conn.commit(); conn.close()

# 已处理媒体（去重）
def add_seen(source, fid):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("INSERT INTO seen (source, file_unique_id) VALUES (?, ?)", (source, fid))
    conn.commit(); conn.close()

def has_seen(source, fid):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT 1 FROM seen WHERE source=? AND file_unique_id=?", (source, fid))
    r = c.fetchone(); conn.close()
    return r is not None

# 组合规则
def add_rule(chat_id: str, rule: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("INSERT INTO rules (chat_id, rule) VALUES (?, ?)", (chat_id, rule))
    conn.commit(); conn.close()

def delete_rule(chat_id: str, rule: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("DELETE FROM rules WHERE chat_id=? AND rule=?", (chat_id, rule))
    conn.commit(); conn.close()

def clear_rules(chat_id: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("DELETE FROM rules WHERE chat_id=?", (chat_id,))
    conn.commit(); conn.close()

def get_rules(chat_id: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT rule FROM rules WHERE chat_id=?", (chat_id,))
    rows = c.fetchall(); conn.close()
    return [r[0] for r in rows]

# 群组信息
def save_chat(chat_id: str, title: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("REPLACE INTO chats (chat_id, title) VALUES (?, ?)", (chat_id, title))
    conn.commit(); conn.close()

# 关键词
def add_keyword(chat_id: str, word: str, is_regex: bool = False):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("INSERT INTO keywords (chat_id, word, is_regex) VALUES (?, ?, ?)", (chat_id, word, int(is_regex)))
    conn.commit(); conn.close()

def get_keywords(chat_id: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT word, is_regex FROM keywords WHERE chat_id=?", (chat_id,))
    rows = c.fetchall(); conn.close()
    return [(r[0], bool(r[1])) for r in rows]

def delete_keyword(chat_id: str, word: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("DELETE FROM keywords WHERE chat_id=? AND word=?", (chat_id, word))
    conn.commit(); conn.close()

# 锁定
def lock_chat(chat_id: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("REPLACE INTO locked (chat_id) VALUES (?)", (chat_id,))
    conn.commit(); conn.close()

def unlock_chat(chat_id: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("DELETE FROM locked WHERE chat_id=?", (chat_id,))
    conn.commit(); conn.close()

def is_locked(chat_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT 1 FROM locked WHERE chat_id=?", (chat_id,))
    r = c.fetchone(); conn.close()
    return r is not None

# 统计
def inc_stat(chat_id: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("""
        INSERT INTO stats (chat_id, count) VALUES (?, 1)
        ON CONFLICT(chat_id) DO UPDATE SET count = count + 1
    """, (chat_id,))
    conn.commit(); conn.close()

def get_stats():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT chat_id, count FROM stats ORDER BY count DESC")
    rows = c.fetchall(); conn.close()
    return rows

# 管理员
def add_admin(user_id: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit(); conn.close()

def delete_admin(user_id: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
    conn.commit(); conn.close()

def list_admins():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT user_id FROM admins ORDER BY user_id")
    rows = c.fetchall(); conn.close()
    return [r[0] for r in rows]