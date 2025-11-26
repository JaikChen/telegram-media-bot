# handlers/sys_admin.py
import os
import sqlite3
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from telegram.error import BadRequest, Forbidden
from config import ADMIN_IDS, DB_FILE
from db import *
from handlers.utils import is_global_admin

async def handle_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    args = msg.text.strip().split()
    if len(args) == 2:
        add_admin(args[1])
        await msg.reply_text(f"✅ 已添加动态管理员：{args[1]}")
    else: await msg.reply_text("❌ 用法：/addadmin ID")

async def handle_deladmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    args = msg.text.strip().split()
    if len(args) == 2:
        delete_admin(args[1])
        await msg.reply_text(f"🗑 已移除：{args[1]}")
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
            details.append(f"`{cid}` {title or '未命名'}")
        except Exception: pass
    if count > 0:
        await status_msg.edit_text(f"✅ 清理了 {count} 个无效群组：\n" + "\n".join(details), parse_mode="Markdown")
    else:
        await status_msg.edit_text("✅ 无无效群组")

async def handle_cleandb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    status_msg = await msg.reply_text("⏳ 维护中...")
    deleted = clean_expired_data(days=3650)
    vacuum_db()
    await status_msg.edit_text(f"✅ 完成！清理过期数据 {deleted} 条，已 VACUUM。")

async def handle_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    args = msg.text.strip().split()
    if len(args) == 2:
        try:
            await context.bot.leave_chat(args[1])
            await msg.reply_text(f"👋 已退出 `{args[1]}`", parse_mode="Markdown")
        except Exception as e: await msg.reply_text(f"❌ 失败: {e}")
    else: await msg.reply_text("❌ 用法：/leave -100xxx")