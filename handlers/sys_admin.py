# handlers/sys_admin.py
# 系统管理命令：管理员管理、数据库、日志、强制操作

import os
import io
import sqlite3
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from telegram.error import BadRequest, Forbidden
from config import ADMIN_IDS, DB_FILE
from db import *
from handlers.utils import is_global_admin

# =========================
# 管理员管理
# =========================
async def handle_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id):
        if msg: await msg.reply_text("🚫 此命令仅限固定配置的管理员使用。")
        return
    args = msg.text.strip().split()
    if len(args) == 2:
        add_admin(args[1])
        await msg.reply_text(f"✅ 已添加动态管理员：{args[1]}")
    else:
        await msg.reply_text("❌ 用法错误：/addadmin 用户ID")

async def handle_deladmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id):
        if msg: await msg.reply_text("🚫 此命令仅限固定配置的管理员使用。")
        return
    args = msg.text.strip().split()
    if len(args) == 2:
        delete_admin(args[1])
        await msg.reply_text(f"🗑 已移除动态管理员：{args[1]}")
    else:
        await msg.reply_text("❌ 用法错误：/deladmin 用户ID")

async def handle_listadmins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
    admins = list_admins()
    fixed = sorted(ADMIN_IDS)
    reply = "👑 管理员列表：\n\n"
    reply += "• 固定管理员（config）：\n" + "\n".join(f"  - {a}" for a in fixed) + "\n\n"
    reply += "• 动态管理员（数据库）：\n" + ("\n".join(f"  - {a}" for a in admins) if admins else "  - (空)")
    await msg.reply_text(reply)

# =========================
# 数据库操作
# =========================
async def handle_backupdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id): return
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
    if not msg or not is_global_admin(msg.from_user.id): return
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
# 日志管理
# =========================
async def handle_setlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id):
        if msg: await msg.reply_text("🚫 此命令仅限固定配置的管理员使用。")
        return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        set_log_channel(chat_id)
        await msg.reply_text(f"✅ 已将频道 `{chat_id}` 设置为日志频道", parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id, "📡 日志通道测试消息：配置成功！")
        except Exception as e:
            await msg.reply_text(f"⚠️ 设置成功，但发送测试消息失败：{e}\n请确保 Bot 是该频道的管理员。")
    else:
        await msg.reply_text("❌ 用法错误：/setlog -100频道ID")

async def handle_dellog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id):
        if msg: await msg.reply_text("🚫 此命令仅限固定配置的管理员使用。")
        return
    set_log_channel("")
    await msg.reply_text("✅ 已关闭日志频道功能")

# =========================
# 强制清理与退出
# =========================
async def handle_cleanchats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id):
        if msg: await msg.reply_text("🚫 此命令仅限固定配置的管理员使用。")
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT chat_id, title FROM chats")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await msg.reply_text("📭 数据库中没有记录任何群组。")
        return
    status_msg = await msg.reply_text(f"⏳ 正在检查 {len(rows)} 个群组的状态，请稍候...")
    cleaned_count = 0
    cleaned_details = []
    for chat_id, title in rows:
        try:
            await context.bot.get_chat(chat_id)
        except (BadRequest, Forbidden) as e:
            delete_chat_data(chat_id)
            cleaned_count += 1
            name = title if title else "未命名"
            error_reason = "群组不存在" if isinstance(e, BadRequest) else "Bot被踢出"
            cleaned_details.append(f"`{chat_id}` {name} ({error_reason})")
        except Exception as e:
            print(f"[Check] 检查群组 {chat_id} 时出错: {e}")
            continue
    if cleaned_count > 0:
        reply = f"✅ 清理完成！共移除 {cleaned_count} 个无效群组：\n\n"
        reply += "\n".join(f"• {line}" for line in cleaned_details)
        await status_msg.edit_text(reply, parse_mode="Markdown")
    else:
        await status_msg.edit_text("✅ 检查完成，数据库中的所有群组均有效。")

async def handle_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id):
        if msg: await msg.reply_text("🚫 此命令仅限固定配置的管理员使用。")
        return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        try:
            await context.bot.leave_chat(chat_id)
            await msg.reply_text(f"👋 Bot 已成功退出频道/群组：`{chat_id}`", parse_mode="Markdown")
        except Exception as e:
            await msg.reply_text(f"❌ 退出失败：{e}")
    else:
        await msg.reply_text("❌ 用法错误：/leave -100频道ID")