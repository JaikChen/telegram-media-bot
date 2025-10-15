# handlers/commands.py
# 处理所有私聊命令，仅限管理员使用（固定管理员 + 动态管理员）

import io
import os
import sqlite3
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from config import ADMIN_IDS, DB_FILE
from db import *
from cleaner import clean_caption

# 判断管理员
async def is_admin(msg):
    uid = str(msg.from_user.id)
    if uid in ADMIN_IDS:
        return True
    try:
        return uid in set(list_admins())
    except Exception:
        return False

# =========================
# 组合规则管理
# =========================

async def handle_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置频道规则（覆盖式）"""
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
        await msg.reply_text(
            "❌ 用法错误：/setrules -100频道ID 规则1,规则2,...\n\n"
            "说明：为频道设置清理规则（覆盖原有规则）\n"
            "示例：/setrules -100123456789 clean_links,remove_at_prefix,block_keywords,maxlen:80"
        )

async def handle_addrule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """增加单条规则"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id, rule = args[1], args[2]
        add_rule(chat_id, rule)
        await msg.reply_text(f"✅ 已为频道 {chat_id} 增加规则：{rule}")
    else:
        await msg.reply_text(
            "❌ 用法错误：/addrule -100频道ID 规则\n\n"
            "说明：为频道增加一条规则\n"
            "示例：/addrule -100123456789 maxlen:100"
        )

async def handle_delrule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """删除单条规则"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id, rule = args[1], args[2]
        delete_rule(chat_id, rule)
        await msg.reply_text(f"🗑 已为频道 {chat_id} 删除规则：{rule}")
    else:
        await msg.reply_text(
            "❌ 用法错误：/delrule -100频道ID 规则\n\n"
            "说明：删除频道的一条规则\n"
            "示例：/delrule -100123456789 strip_all_if_links"
        )

async def handle_listrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出规则"""
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
        await msg.reply_text(
            "❌ 用法错误：/listrules -100频道ID\n\n"
            "说明：查看频道的规则列表\n"
            "示例：/listrules -100123456789"
        )

async def handle_clearrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """清空规则"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        clear_rules(args[1])
        await msg.reply_text(f"🧹 已清空频道 {args[1]} 的所有规则")
    else:
        await msg.reply_text(
            "❌ 用法错误：/clearrules -100频道ID\n\n"
            "说明：清空频道的所有规则\n"
            "示例：/clearrules -100123456789"
        )

# =========================
# 群组管理
# =========================

async def handle_listchats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出 Bot 所在频道/群组"""
    msg = update.message
    if not msg or not await is_admin(msg): return
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
    """查看频道信息"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        title = "(未记录名称)"
        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
        c.execute("SELECT title FROM chats WHERE chat_id=?", (args[1],))
        r = c.fetchone(); conn.close()
        if r: title = r[0]
        rules = get_rules(args[1])
        details = f"• 规则：{', '.join(rules) or '(未设置)'}"
        await msg.reply_text(f"📍 频道信息：\n• ID：{args[1]}\n• 名称：{title}\n{details}")
    else:
        await msg.reply_text(
            "❌ 用法错误：/chatinfo -100频道ID\n\n"
            "说明：查看频道的名称和规则\n"
            "示例：/chatinfo -100123456789"
        )

# =========================
# 说明预览
# =========================

async def handle_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """预览说明清理效果"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        cleaned = clean_caption(args[2], args[1])
        await msg.reply_text(f"🧹 清理结果：\n\n{cleaned or '(说明已被完全移除)'}")
    else:
        await msg.reply_text(
            "❌ 用法错误：/preview -100频道ID 说明文字\n\n"
            "说明：测试说明文字清理效果\n"
            "示例：/preview -100123456789 这是一个测试说明"
        )
# =========================
# 关键词管理
# =========================

async def handle_addkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """添加关键词"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=3)
    if len(args) >= 3:
        is_regex = (len(args) == 4 and args[3].lower() == "regex")
        add_keyword(args[1], args[2], is_regex=is_regex)
        await msg.reply_text(
            f"✅ 已添加关键词 `{args[2]}` 到频道 {args[1]}{' (regex)' if is_regex else ''}",
            parse_mode="Markdown"
        )
    else:
        await msg.reply_text(
            "❌ 用法错误：/addkw -100频道ID 关键词 [regex]\n\n"
            "说明：为频道添加关键词，可选 regex 模式\n"
            "示例：/addkw -100123456789 广告\n"
            "示例：/addkw -100123456789 \\d{11} regex"
        )

async def handle_listkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出关键词"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        kws = get_keywords(args[1])
        if not kws:
            await msg.reply_text("📭 当前频道没有设置任何关键词。")
            return
        reply = f"📋 频道 {args[1]} 的关键词列表：\n\n" + "\n".join(
            f"• {w}{' (regex)' if is_regex else ''}" for w, is_regex in kws
        )
        await msg.reply_text(reply.strip())
    else:
        await msg.reply_text("❌ 用法错误：/listkw -100频道ID")

async def handle_delkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """删除关键词"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        delete_keyword(args[1], args[2])
        await msg.reply_text(f"🗑 已删除频道 {args[1]} 的关键词 `{args[2]}`", parse_mode="Markdown")
    else:
        await msg.reply_text("❌ 用法错误：/delkw -100频道ID 关键词")

async def handle_exportkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """导出关键词"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        kws = get_keywords(args[1])
        if not kws:
            await msg.reply_text("📭 当前频道没有关键词。")
            return
        buf = io.StringIO()
        for w, is_regex in kws:
            buf.write(f"{w}\t{1 if is_regex else 0}\n")
        buf.seek(0)
        await context.bot.send_document(
            chat_id=msg.chat_id,
            document=InputFile(io.BytesIO(buf.getvalue().encode("utf-8")), filename=f"keywords_{args[1]}.txt"),
            caption=f"📎 频道 {args[1]} 的关键词导出文件"
        )
    else:
        await msg.reply_text("❌ 用法错误：/exportkw -100频道ID")

async def handle_importkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """导入关键词"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)

    # 文本导入
    if len(args) == 3:
        words = [w.strip() for w in args[2].split(",") if w.strip()]
        for w in words:
            add_keyword(args[1], w)
        await msg.reply_text(f"✅ 已为频道 {args[1]} 批量导入 {len(words)} 个关键词")
        return

    # 文件导入
    if msg.document and len(args) == 2:
        chat_id = args[1]
        file = await context.bot.get_file(msg.document.file_id)
        f = io.BytesIO()
        await file.download_to_memory(out=f)
        f.seek(0)
        count = 0
        for line in f.read().decode("utf-8", errors="ignore").splitlines():
            parts = line.strip().split("\t")
            if not parts: continue
            word = parts[0]
            is_regex = (len(parts) > 1 and parts[1] == "1")
            add_keyword(chat_id, word, is_regex=is_regex)
            count += 1
        await msg.reply_text(f"✅ 已从文件为频道 {chat_id} 导入 {count} 个关键词")
    else:
        await msg.reply_text("❌ 用法错误：/importkw -100频道ID 关键词1,关键词2,... 或 回复文件")

# =========================
# 锁定/解锁
# =========================

async def handle_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """锁定频道"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        lock_chat(args[1])
        await msg.reply_text(f"🔒 已锁定频道 {args[1]}，暂停清理")
    else:
        await msg.reply_text("❌ 用法错误：/lock -100频道ID")

async def handle_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """解锁频道"""
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
    """查看统计"""
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
    """添加管理员"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        add_admin(args[1])
        await msg.reply_text(f"✅ 已添加管理员：{args[1]}")
    else:
        await msg.reply_text("❌ 用法错误：/addadmin 用户ID")

async def handle_deladmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """删除管理员"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        delete_admin(args[1])
        await msg.reply_text(f"🗑 已移除管理员：{args[1]}")
    else:
        await msg.reply_text("❌ 用法错误：/deladmin 用户ID")

async def handle_listadmins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出管理员"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    admins = list_admins()
    fixed = sorted(ADMIN_IDS)
    reply = "👑 管理员列表：\n\n"
    reply += "• 固定管理员（config）：\n" + "\n".join(f"  - {a}" for a in fixed) + "\n\n"
    reply += "• 动态管理员（数据库）：\n" + ("\n".join(f"  - {a}" for a in admins) if admins else "  - (空)")
    await msg.reply_text(reply)

# =========================
# 数据库备份与恢复
# =========================

async def handle_backupdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """备份数据库"""
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
    """恢复数据库"""
    msg = update.message
    if not msg or not await is_admin(msg): return
    if not msg.document:
        await msg.reply_text(
            "❌ 用法错误：回复一个数据库文件并输入 /restoredb\n\n"
            "说明：恢复数据库（会覆盖当前数据，建议先 /backupdb 备份）"
        )
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
    """帮助菜单"""
    msg = update.message
    if not msg or not await is_admin(msg):
        return

    await msg.reply_text("""
🤖 Bot 管理命令帮助（带说明和示例）

【组合规则】
/setrules -100频道ID 规则1,规则2,...
  说明：为频道设置清理规则（覆盖原有规则）
  示例：/setrules -100123456789 clean_links,remove_at_prefix,block_keywords,maxlen:80

/addrule -100频道ID 规则
  说明：为频道增加一条规则
  示例：/addrule -100123456789 maxlen:100

/delrule -100频道ID 规则
  说明：删除频道的一条规则
  示例：/delrule -100123456789 strip_all_if_links

/listrules -100频道ID
  说明：查看频道的规则列表
  示例：/listrules -100123456789

/clearrules -100频道ID
  说明：清空频道的所有规则
  示例：/clearrules -100123456789

可用规则：clean_links, strip_all_if_links, remove_at_prefix, block_keywords, keep_all, maxlen:NN

【群组管理】
/listchats
  说明：列出 Bot 所在的所有频道和群组

/chatinfo -100频道ID
  说明：查看频道的名称和规则
  示例：/chatinfo -100123456789

【说明预览】
/preview -100频道ID 说明文字
  说明：测试说明文字清理效果
  示例：/preview -100123456789 这是一个测试说明

【关键词管理】
/addkw -100频道ID 关键词 [regex]
  说明：为频道添加关键词，可选 regex 模式
  示例：/addkw -100123456789 广告
  示例：/addkw -100123456789 \\d{11} regex

/listkw -100频道ID
  说明：查看频道的关键词列表
  示例：/listkw -100123456789

/delkw -100频道ID 关键词
  说明：删除频道的关键词
  示例：/delkw -100123456789 广告

/exportkw -100频道ID
  说明：导出频道的关键词列表为文件
  示例：/exportkw -100123456789

/importkw -100频道ID 关键词1,关键词2,...
  说明：批量导入关键词（用逗号分隔）
  示例：/importkw -100123456789 广告,推广,微信
  或：回复关键词文件并输入 /importkw -100频道ID

【锁定/解锁】
/lock -100频道ID
  说明：锁定频道，暂停清理
  示例：/lock -100123456789

/unlock -100频道ID
  说明：解锁频道，恢复清理
  示例：/unlock -100123456789

【统计】
/stats
  说明：查看所有频道的清理统计数据

【管理员管理】
/addadmin 用户ID
  说明：添加动态管理员
  示例：/addadmin 123456789

/deladmin 用户ID
  说明：移除动态管理员
  示例：/deladmin 123456789

/listadmins
  说明：查看固定管理员和动态管理员列表

【数据库】
/backupdb
  说明：导出数据库备份文件

/restoredb
  说明：恢复数据库（需回复数据库文件）
""".strip())