# handlers/commands.py
# 管理命令：规则、关键词、管理员、转发映射等

from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from db import *
from cleaner import clean_caption

# =========================
# 判断管理员
# =========================
async def is_admin(msg):
    uid = str(msg.from_user.id)
    if uid in ADMIN_IDS:
        return True
    return uid in list_admins()

# =========================
# 组合规则管理
# =========================
async def handle_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id = args[1]
        rule_list = [r.strip() for r in args[2].split(",") if r.strip()]
        clear_rules(chat_id)
        for r in rule_list:
            add_rule(chat_id, r)
        await msg.reply_text(f"✅ 已为频道 {chat_id} 设置规则：{', '.join(rule_list) or '(空)'}")
    else:
        await msg.reply_text("❌ 用法错误：/setrules -100频道ID 规则1,规则2,...")

async def handle_addrule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id, rule = args[1], args[2]
        add_rule(chat_id, rule)
        await msg.reply_text(f"✅ 已为频道 {chat_id} 增加规则：{rule}")
    else:
        await msg.reply_text("❌ 用法错误：/addrule -100频道ID 规则")

async def handle_delrule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id, rule = args[1], args[2]
        delete_rule(chat_id, rule)
        await msg.reply_text(f"🗑 已为频道 {chat_id} 删除规则：{rule}")
    else:
        await msg.reply_text("❌ 用法错误：/delrule -100频道ID 规则")

async def handle_listrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        rules = get_rules(args[1])
        if not rules:
            await msg.reply_text("📭 当前频道未设置任何规则。")
            return
        reply = f"📋 频道 {args[1]} 的规则列表：\n\n" + "\n".join(f"• {r}" for r in rules)
        await msg.reply_text(reply.strip())
    else:
        await msg.reply_text("❌ 用法错误：/listrules -100频道ID")

async def handle_clearrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        clear_rules(args[1])
        await msg.reply_text(f"🧹 已清空频道 {args[1]} 的所有规则")
    else:
        await msg.reply_text("❌ 用法错误：/clearrules -100频道ID")

# =========================
# 群组管理
# =========================
async def handle_listchats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    import sqlite3
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT chat_id, title FROM chats ORDER BY chat_id")
    rows = c.fetchall(); conn.close()
    if not rows:
        await msg.reply_text("📭 当前没有记录任何频道或群组。")
        return
    reply = "📋 Bot 所在频道/群组列表：\n\n"
    for chat_id, title in rows:
        name = title.strip() if title else "(无名称)"
        reply += f"• `{chat_id}` → {name}\n"
    await msg.reply_text(reply.strip(), parse_mode="Markdown")

async def handle_chatinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        title = "(未记录名称)"
        import sqlite3
        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
        c.execute("SELECT title FROM chats WHERE chat_id=?", (args[1],))
        r = c.fetchone(); conn.close()
        if r: title = r[0]
        rules = get_rules(args[1])
        details = f"• 规则：{', '.join(rules) or '(未设置)'}"
        await msg.reply_text(f"📍 频道信息：\n• ID：{args[1]}\n• 名称：{title}\n{details}")
    else:
        await msg.reply_text("❌ 用法错误：/chatinfo -100频道ID")

# =========================
# 说明预览
# =========================
async def handle_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        cleaned = clean_caption(args[2], args[1])
        await msg.reply_text(f"🧹 清理结果：\n\n{cleaned or '(说明已被完全移除)'}")
    else:
        await msg.reply_text("❌ 用法错误：/preview -100频道ID 说明文字")

# =========================
# 关键词管理
# =========================
async def handle_addkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=3)
    if len(args) >= 3:
        is_regex = (len(args) == 4 and args[3].lower() == "regex")
        add_keyword(args[1], args[2], is_regex=is_regex)
        await msg.reply_text(f"✅ 已添加关键词 `{args[2]}` 到频道 {args[1]}{' (regex)' if is_regex else ''}", parse_mode="Markdown")
    else:
        await msg.reply_text("❌ 用法错误：/addkw -100频道ID 关键词 [regex]")

async def handle_listkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        kws = get_keywords(args[1])
        if not kws:
            await msg.reply_text("📭 当前频道没有设置任何关键词。")
            return
        reply = f"📋 频道 {args[1]} 的关键词列表：\n\n" + "\n".join(f"• {w}{' (regex)' if is_regex else ''}" for w, is_regex in kws)
        await msg.reply_text(reply.strip())
    else:
        await msg.reply_text("❌ 用法错误：/listkw -100频道ID")

async def handle_delkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        delete_keyword(args[1], args[2])
        await msg.reply_text(f"🗑 已删除频道 {args[1]} 的关键词 `{args[2]}`", parse_mode="Markdown")
    else:
        await msg.reply_text("❌ 用法错误：/delkw -100频道ID 关键词")

# =========================
# 锁定/解锁
# =========================
async def handle_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        lock_chat(args[1])
        await msg.reply_text(f"🔒 已锁定频道 {args[1]}，暂停清理")
    else:
        await msg.reply_text("❌ 用法错误：/lock -100频道ID")

async def handle_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        unlock_chat(args[1])
        await msg.reply_text(f"🔓 已解锁频道 {args[1]}，恢复清理")
    else:
        await msg.reply_text("❌ 用法错误：/unlock -100频道ID")

# =========================
# 统计
# =========================
async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    rows = get_stats()
    if not rows:
        await msg.reply_text("📭 暂无清理记录。")
        return
    reply = "📊 清理统计：\n\n" + "\n".join(f"• `{cid}` → {count} 次" for cid, count in rows)
    await msg.reply_text(reply.strip(), parse_mode="Markdown")

# =========================
# 管理员管理
# =========================
async def handle_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        add_admin(args[1])
        await msg.reply_text(f"✅ 已添加管理员：{args[1]}")
    else:
        await msg.reply_text("❌ 用法错误：/addadmin 用户ID")

async def handle_deladmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        delete_admin(args[1])
        await msg.reply_text(f"🗑 已移除管理员：{args[1]}")
    else:
        await msg.reply_text("❌ 用法错误：/deladmin 用户ID")

async def handle_listadmins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    admins = list_admins()
    fixed = sorted(ADMIN_IDS)
    reply = "👑 管理员列表：\n\n"
    reply += "• 固定管理员（config）：\n" + "\n".join(f"  - {a}" for a in fixed) + "\n\n"
    reply += "• 动态管理员（数据库）：\n" + ("\n".join(f"  - {a}" for a in admins) if admins else "  - (空)")
    await msg.reply_text(reply)

# =========================
# 转发映射命令
# =========================
async def handle_addforward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        add_forward(args[1], args[2])
        await msg.reply_text(f"✅ 已添加转发映射：{args[1]} → {args[2]}")
    else:
        await msg.reply_text("❌ 用法错误：/addforward -100源频道ID -100目标频道ID")

async def handle_delforward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        del_forward(args[1], args[2])
        await msg.reply_text(f"🗑 已移除转发映射：{args[1]} → {args[2]}")
    else:
        await msg.reply_text("❌ 用法错误：/delforward -100源频道ID -100目标频道ID")

async def handle_listforward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        targets = list_forward(args[1])
        if not targets:
            await msg.reply_text(f"📭 频道 {args[1]} 暂无转发目标。")
            return
        reply = "📦 转发映射列表：\n\n" + "\n".join(f"• {args[1]} → {t}" for t in targets)
        await msg.reply_text(reply)
    else:
        await msg.reply_text("❌ 用法错误：/listforward -100源频道ID")


# =========================
# 数据库备份与恢复
# =========================
import os, io
from telegram import InputFile

async def handle_backupdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    if not os.path.exists(DB_FILE):
        await msg.reply_text("❌ 未找到数据库文件。")
        return
    await context.bot.send_document(
        chat_id=msg.chat_id,
        document=InputFile(open(DB_FILE, "rb"), filename=os.path.basename(DB_FILE)),
        caption="📦 数据库备份"
    )

async def handle_restoredb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    if not msg.document:
        await msg.reply_text("❌ 用法错误：回复一个数据库文件并输入 /restoredb")
        return
    file = await context.bot.get_file(msg.document.file_id)
    tmp = io.BytesIO()
    await file.download_to_memory(out=tmp)
    tmp.seek(0)
    with open(DB_FILE, "wb") as f:
        f.write(tmp.read())
    await msg.reply_text("✅ 数据库已恢复")

# =========================
# 帮助
# =========================
async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg):
        return
    await msg.reply_text("""
🤖 *Bot 管理命令帮助*

📌 所有命令仅限管理员使用，频道 ID 请使用 `-100` 开头格式。以下命令可直接点击复制使用：

*🧩 组合规则管理*
`/setrules -100频道ID 规则1,规则2,...` - 设置频道规则（覆盖原有）
`/addrule -100频道ID 规则` - 添加单条规则
`/delrule -100频道ID 规则` - 删除指定规则
`/listrules -100频道ID` - 查看规则列表
`/clearrules -100频道ID` - 清空所有规则

📖 *规则示例*：
- `keep_all`：保留所有说明文字  
- `strip_all_if_links`：如含链接则整段删除  
- `clean_links`：清除链接但保留文字  
- `remove_at_prefix`：删除 @前缀  
- `block_keywords`：启用关键词屏蔽  
- `maxlen:50`：说明文字超过 50 字则删除

*🔑 关键词管理*
`/addkw -100频道ID 关键词 [regex]` - 添加关键词（支持正则）
`/delkw -100频道ID 关键词` - 删除关键词
`/listkw -100频道ID` - 查看关键词列表

*🔒 清理控制*
`/lock -100频道ID` - 锁定频道，暂停清理
`/unlock -100频道ID` - 解锁频道，恢复清理

*📊 清理统计*
`/stats` - 查看各频道清理次数

*👑 管理员管理*
`/addadmin 用户ID` - 添加动态管理员
`/deladmin 用户ID` - 移除动态管理员
`/listadmins` - 查看所有管理员（固定+动态）

*🔁 转发映射*
`/addforward -100源频道ID -100目标频道ID` - 添加转发映射
`/delforward -100源频道ID -100目标频道ID` - 删除转发映射
`/listforward -100源频道ID` - 查看转发目标列表
*🧹 说明预览*
`/preview -100频道ID 说明文字` - 模拟清理说明，查看结果

*🧭 群组管理*
`/listchats` - 查看 Bot 所在频道/群组列表
`/chatinfo -100频道ID` - 查看频道信息（名称+规则）

*💾 数据库操作*
`/backupdb` - 备份数据库文件
`/restoredb` - 恢复数据库（需回复数据库文件）
""".strip(), parse_mode="Markdown")