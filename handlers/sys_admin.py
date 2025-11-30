# handlers/sys_admin.py
import os
import sqlite3
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from telegram.error import BadRequest, Forbidden
from config import ADMIN_IDS, DB_FILE
from db import *
from handlers.utils import is_global_admin, log_event, escape_markdown

async def handle_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    args = msg.text.strip().split()
    if len(args) == 2:
        add_admin(args[1])
        await msg.reply_text(f"✅ 已添加动态管理员：{args[1]}")
        await log_event(context.bot, f"添加管理员: {args[1]}", category="system")
    else: await msg.reply_text("❌ 用法：/addadmin ID")

async def handle_deladmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    args = msg.text.strip().split()
    if len(args) == 2:
        delete_admin(args[1])
        await msg.reply_text(f"🗑 已移除：{args[1]}")
        await log_event(context.bot, f"移除管理员: {args[1]}", category="system")
    else: await msg.reply_text("❌ 用法：/deladmin ID")

async def handle_listadmins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    admins = list_admins()
    fixed = sorted(ADMIN_IDS)
    reply = "👑 管理员列表：\n\n• 固定：\n" + "\n".join(f" - {a}" for a in fixed)
    reply += "\n\n• 动态：\n" + ("\n".join(f" - {a}" for a in admins) if admins else " - (空)")
    await msg.reply_text(reply)

async def handle_backupdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    if not os.path.exists(DB_FILE): await msg.reply_text("❌ 无数据库"); return
    await context.bot.send_document(chat_id=msg.chat_id, document=InputFile(open(DB_FILE, "rb"), filename=os.path.basename(DB_FILE)), caption="📦 备份")
    await log_event(context.bot, "管理员执行了数据库备份", category="system")

async def handle_restoredb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    if not msg.document: await msg.reply_text("❌ 请回复数据库文件"); return
    file = await context.bot.get_file(msg.document.file_id)
    import io
    tmp = io.BytesIO()
    await file.download_to_memory(out=tmp)
    tmp.seek(0)
    with open(DB_FILE, "wb") as f: f.write(tmp.read())
    await msg.reply_text("✅ 已恢复")
    await log_event(context.bot, "管理员执行了数据库恢复", category="system")

async def handle_setlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    args = msg.text.strip().split()
    if len(args) == 2:
        set_log_channel(args[1])
        await msg.reply_text(f"✅ 日志频道：`{args[1]}`", parse_mode="Markdown")
        try: await context.bot.send_message(args[1], "📡 测试消息")
        except Exception as e: await msg.reply_text(f"⚠️ 无法发送测试消息: {e}")
    else: await msg.reply_text("❌ 用法：/setlog -100xxx")

async def handle_dellog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    set_log_channel("")
    await msg.reply_text("✅ 已关闭日志")

async def handle_setlogfilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    args = msg.text.strip().split()
    valid_types = ['clean', 'duplicate', 'forward', 'error', 'system']
    if len(args) == 1:
        current = get_log_filter()
        await msg.reply_text(f"📝 当前日志过滤：\n`{', '.join(current)}`\n\n可用类型：`{' '.join(valid_types)}`", parse_mode="Markdown")
        return
    new_types = [t for t in args[1:] if t in valid_types]
    if not new_types:
        await msg.reply_text(f"❌ 无效类型。请从以下选择：\n`{' '.join(valid_types)}`", parse_mode="Markdown")
        return
    set_log_filter(new_types)
    await msg.reply_text(f"✅ 日志过滤已更新：\n`{', '.join(new_types)}`", parse_mode="Markdown")

async def handle_cleanchats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT chat_id, title FROM chats")
    rows = c.fetchall(); conn.close()
    if not rows: await msg.reply_text("📭 无群组记录"); return
    status_msg = await msg.reply_text(f"⏳ 检查 {len(rows)} 个群组...")
    count = 0
    details = []
    for cid, title in rows:
        try: await context.bot.get_chat(cid)
        except (BadRequest, Forbidden):
            delete_chat_data(cid)
            count += 1
            safe_title = escape_markdown(title or '未命名')
            details.append(f"`{cid}` {safe_title}")
        except Exception: pass
    if count > 0:
        await status_msg.edit_text(f"✅ 清理了 {count} 个无效群组：\n" + "\n".join(details), parse_mode="Markdown")
        await log_event(context.bot, f"清理了 {count} 个无效群组", category="system")
    else:
        await status_msg.edit_text("✅ 无无效群组")

async def handle_cleandb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    status_msg = await msg.reply_text("⏳ 正在清理过期数据并整理数据库...")
    deleted = clean_expired_data(days=365)
    vacuum_db()
    await status_msg.edit_text(f"✅ 数据库维护完成！\n\n🗑 已删除 {deleted} 条过期去重记录 (1年前)\n🧹 已执行 VACUUM 碎片整理")
    await log_event(context.bot, f"手动执行数据库维护，清理 {deleted} 条记录", category="system")

async def handle_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    args = msg.text.strip().split()
    if len(args) == 2:
        try:
            await context.bot.leave_chat(args[1])
            await msg.reply_text(f"👋 已退出 `{args[1]}`", parse_mode="Markdown")
            await log_event(context.bot, f"强制退出群组: {args[1]}", category="system")
        except Exception as e: await msg.reply_text(f"❌ 失败: {e}")
    else: await msg.reply_text("❌ 用法：/leave -100xxx")