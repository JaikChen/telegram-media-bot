import sqlite3
from config import DB_FILE

# =========================
# 初始化数据库结构
# =========================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 已处理媒体记录（用于频道内去重）
    c.execute("""
        CREATE TABLE IF NOT EXISTS seen (
            chat_id TEXT,
            file_unique_id TEXT,
            PRIMARY KEY (chat_id, file_unique_id)
        )
    """)

    # 频道/群组信息（记录名称）
    c.execute("CREATE TABLE IF NOT EXISTS chats (chat_id TEXT PRIMARY KEY, title TEXT)")

    # 关键词屏蔽规则
    c.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            chat_id TEXT,
            word TEXT,
            is_regex INTEGER DEFAULT 0
        )
    """)

    # 锁定状态（暂停清理）
    c.execute("CREATE TABLE IF NOT EXISTS locked (chat_id TEXT PRIMARY KEY)")

    # 清理统计（记录次数）
    c.execute("CREATE TABLE IF NOT EXISTS stats (chat_id TEXT PRIMARY KEY, count INTEGER)")

    # 组合规则（说明清理规则）
    c.execute("CREATE TABLE IF NOT EXISTS rules (chat_id TEXT, rule TEXT)")

    # 动态管理员列表
    c.execute("CREATE TABLE IF NOT EXISTS admins (user_id TEXT PRIMARY KEY)")

    # 转发映射关系（源频道 → 目标频道）
    c.execute("""
        CREATE TABLE IF NOT EXISTS forward_map (
            source_chat_id TEXT,
            target_chat_id TEXT,
            PRIMARY KEY (source_chat_id, target_chat_id)
        )
    """)

    # ✅ 新增：转发去重记录（目标频道已接收的媒体）
    c.execute("""
        CREATE TABLE IF NOT EXISTS forward_seen (
            chat_id TEXT,
            file_unique_id TEXT,
            PRIMARY KEY (chat_id, file_unique_id)
        )
    """)

    conn.commit()
    conn.close()

# =========================
# 已处理媒体（频道内去重）
# =========================
def add_seen(chat_id: str, fid: str):
    """记录某频道已处理的媒体唯一 ID"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO seen (chat_id, file_unique_id) VALUES (?, ?)", (chat_id, fid))
    except sqlite3.IntegrityError:
        pass
    conn.commit()
    conn.close()

def has_seen(chat_id: str, fid: str) -> bool:
    """检查某频道是否已处理该媒体"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM seen WHERE chat_id=? AND file_unique_id=?", (chat_id, fid))
    r = c.fetchone()
    conn.close()
    return r is not None

# =========================
# 转发去重记录（目标频道）
# =========================
def add_forward_seen(chat_id: str, fid: str):
    """记录某目标频道已接收的媒体"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO forward_seen (chat_id, file_unique_id) VALUES (?, ?)", (chat_id, fid))
    except sqlite3.IntegrityError:
        pass
    conn.commit()
    conn.close()

def has_forward_seen(chat_id: str, fid: str) -> bool:
    """检查目标频道是否已接收该媒体"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM forward_seen WHERE chat_id=? AND file_unique_id=?", (chat_id, fid))
    r = c.fetchone()
    conn.close()
    return r is not None

# =========================
# 清理规则管理
# =========================
def add_rule(chat_id: str, rule: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO rules (chat_id, rule) VALUES (?, ?)", (chat_id, rule))
    conn.commit()
    conn.close()

def delete_rule(chat_id: str, rule: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM rules WHERE chat_id=? AND rule=?", (chat_id, rule))
    conn.commit()
    conn.close()

def clear_rules(chat_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM rules WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()

def get_rules(chat_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT rule FROM rules WHERE chat_id=?", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

# =========================
# 关键词管理
# =========================
def add_keyword(chat_id: str, word: str, is_regex: bool = False):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO keywords (chat_id, word, is_regex) VALUES (?, ?, ?)",
        (chat_id, word, 1 if is_regex else 0)
    )
    conn.commit()
    conn.close()

def delete_keyword(chat_id: str, word: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM keywords WHERE chat_id=? AND word=?", (chat_id, word))
    conn.commit()
    conn.close()

def get_keywords(chat_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT word, is_regex FROM keywords WHERE chat_id=?", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return [(w, bool(r)) for w, r in rows]

# =========================
# 锁定频道（暂停清理）
# =========================
def lock_chat(chat_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO locked (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()

def unlock_chat(chat_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM locked WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()

def is_locked(chat_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM locked WHERE chat_id=?", (chat_id,))
    r = c.fetchone()
    conn.close()
    return r is not None

# =========================
# 清理统计
# =========================
def inc_stat(chat_id: str):
    """增加频道清理次数（自动累加）"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO stats (chat_id, count) VALUES (?, 1) "
        "ON CONFLICT(chat_id) DO UPDATE SET count=count+1",
        (chat_id,)
    )
    conn.commit()
    conn.close()

def get_stats():
    """获取所有频道清理统计"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT chat_id, count FROM stats ORDER BY count DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# =========================
# 管理员管理
# =========================
def add_admin(user_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def delete_admin(user_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def list_admins():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id FROM admins")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

# =========================
# 群组/频道信息
# =========================
def save_chat(chat_id: str, title: str):
    """保存频道名称"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO chats (chat_id, title) VALUES (?, ?)", (chat_id, title))
    conn.commit()
    conn.close()

# =========================
# 转发映射管理
# =========================
def add_forward(source_chat_id: str, target_chat_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO forward_map (source_chat_id, target_chat_id) VALUES (?, ?)",
        (source_chat_id, target_chat_id)
    )
    conn.commit()
    conn.close()

def del_forward(source_chat_id: str, target_chat_id: str):
    """删除转发映射关系"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM forward_map WHERE source_chat_id=? AND target_chat_id=?", (source_chat_id, target_chat_id))
    conn.commit()
    conn.close()

def list_forward(source_chat_id: str):
    """列出某源频道的所有转发目标"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT target_chat_id FROM forward_map WHERE source_chat_id=?", (source_chat_id,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_forward_targets(source_chat_id: str):
    """获取某频道的转发目标列表（别名）"""
    return list_forward(source_chat_id)