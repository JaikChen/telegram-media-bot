# handlers/sys_admin.py
import os
import sqlite3
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from telegram.error import BadRequest, Forbidden
from config import ADMIN_IDS, DB_FILE
from db import *
from handlers.utils import is_global_admin, log_event, escape_markdown, admin_only
from locales import get_text
from handlers.media import forward_worker  # [新增] 导入Worker以进行恢复


@admin_only
async def handle_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id): return
    if len(context.args) < 1:
        await update.message.reply_text(get_text("args_error"))
        return
    await add_admin(context.args[0])
    await update.message.reply_text(get_text("admin_added", context.args[0]))
    await log_event(context.bot, f"添加管理员: {context.args[0]}", category="system")


@admin_only
async def handle_deladmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id): return
    if len(context.args) < 1:
        await update.message.reply_text(get_text("args_error"))
        return
    await delete_admin(context.args[0])
    await update.message.reply_text(get_text("admin_deleted", context.args[0]))
    await log_event(context.bot, f"移除管理员: {context.args[0]}", category="system")


@admin_only
async def handle_listadmins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id): return
    admins = await list_admins()
    fixed = sorted(ADMIN_IDS)
    reply = "👑 管理员列表：\n\n• 固定：\n" + "\n".join(f" - {a}" for a in fixed)
    reply += "\n\n• 动态：\n" + ("\n".join(f" - {a}" for a in admins) if admins else " - (空)")
    await update.message.reply_text(reply)


@admin_only
async def handle_backupdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id): return
    if not os.path.exists(DB_FILE):
        await update.message.reply_text("❌ 无数据库")
        return
    await context.bot.send_document(chat_id=update.message.chat_id,
                                    document=InputFile(open(DB_FILE, "rb"), filename=os.path.basename(DB_FILE)),
                                    caption=get_text("backup_caption"))
    await log_event(context.bot, "管理员执行了数据库备份", category="system")


@admin_only
async def handle_restoredb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id): return
    msg = update.message
    if not msg.document:
        await msg.reply_text("❌ 请回复数据库文件")
        return
    file = await context.bot.get_file(msg.document.file_id)
    import io
    tmp = io.BytesIO()
    await file.download_to_memory(out=tmp)
    tmp.seek(0)
    with open(DB_FILE, "wb") as f:
        f.write(tmp.read())
    await msg.reply_text(get_text("restore_success"))
    await log_event(context.bot, "管理员执行了数据库恢复", category="system")


@admin_only
async def handle_setlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id): return
    if len(context.args) < 1:
        await update.message.reply_text("❌ 用法：`/setlog -100xxx`", parse_mode="Markdown")
        return
    await set_log_channel(context.args[0])
    await update.message.reply_text(get_text("log_set", context.args[0]), parse_mode="Markdown")
    try:
        await context.bot.send_message(context.args[0], "📡 测试消息")
    except Exception as e:
        await update.message.reply_text(f"⚠️ 无法发送测试消息: {e}")


@admin_only
async def handle_dellog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id): return
    await set_log_channel("")
    await update.message.reply_text(get_text("log_off"))


@admin_only
async def handle_setlogfilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id): return
    valid_types = ['clean', 'duplicate', 'forward', 'error', 'system']
    if len(context.args) < 1:
        current = await get_log_filter()
        await update.message.reply_text(
            f"📝 当前日志过滤：\n`{', '.join(current)}`\n\n可用类型：`{' '.join(valid_types)}`", parse_mode="Markdown")
        return
    new_types = [t for t in context.args if t in valid_types]
    if not new_types:
        await update.message.reply_text(get_text("args_error"), parse_mode="Markdown")
        return
    await set_log_filter(new_types)
    await update.message.reply_text(f"✅ 日志过滤已更新：\n`{', '.join(new_types)}`", parse_mode="Markdown")


@admin_only
async def handle_cleanchats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id): return
    rows = await execute_sql("SELECT chat_id, title FROM chats", fetchall=True)
    if not rows:
        await update.message.reply_text(get_text("no_data"))
        return
    status_msg = await update.message.reply_text(f"⏳ 检查 {len(rows)} 个群组...")
    count = 0
    details = []
    for cid, title in rows:
        try:
            await context.bot.get_chat(cid)
        except (BadRequest, Forbidden):
            await delete_chat_data(cid)
            count += 1
            safe_title = escape_markdown(title or '未命名')
            details.append(f"`{cid}` {safe_title}")
        except Exception:
            pass
    if count > 0:
        await status_msg.edit_text(f"✅ 清理了 {count} 个无效群组：\n" + "\n".join(details), parse_mode="Markdown")
        await log_event(context.bot, f"清理了 {count} 个无效群组", category="system")
    else:
        await status_msg.edit_text("✅ 无无效群组")


@admin_only
async def handle_cleandb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id): return
    status_msg = await update.message.reply_text("⏳ 正在清理过期数据并整理数据库...")
    deleted = await clean_expired_data(days=365)
    await vacuum_db()
    await status_msg.edit_text(get_text("maintenance_complete", deleted))
    await log_event(context.bot, f"手动执行数据库维护，清理 {deleted} 条记录", category="system")


@admin_only
async def handle_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id): return
    if len(context.args) < 1:
        await update.message.reply_text("❌ 用法：`/leave -100xxx`", parse_mode="Markdown")
        return
    try:
        await context.bot.leave_chat(context.args[0])
        await update.message.reply_text(f"👋 已退出 `{context.args[0]}`", parse_mode="Markdown")
        await log_event(context.bot, f"强制退出群组: {context.args[0]}", category="system")
    except Exception as e:
        await update.message.reply_text(f"❌ 失败: {e}")


@admin_only
async def handle_setdelay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id): return
    if len(context.args) == 0:
        min_s, max_s = await get_delay_settings()
        if min_s == 0 and max_s == 0:
            await update.message.reply_text("⏱ 当前设置：**无延迟** (实时转发)", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⏱ 当前设置：**{min_s} ~ {max_s} 秒** 随机延迟", parse_mode="Markdown")
        return

    if len(context.args) == 2:
        try:
            min_s = int(context.args[0])
            max_s = int(context.args[1])
            if min_s < 0 or max_s < min_s: raise ValueError
            await set_delay_settings(min_s, max_s)
            if min_s == 0 and max_s == 0:
                await update.message.reply_text("✅ 已关闭延迟，恢复实时转发。")
            else:
                await update.message.reply_text(f"✅ 已设置转发延迟：**{min_s} ~ {max_s} 秒**", parse_mode="Markdown")
                await log_event(context.bot, f"更新转发延迟为 {min_s}-{max_s}s", category="system")
        except ValueError:
            await update.message.reply_text("❌ 错误：请输入有效的整数，且 min <= max。\n示例：`/setdelay 60 120`",
                                            parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ 用法：`/setdelay min max` (单位秒，0 0 关闭)", parse_mode="Markdown")


# [新增] 暂停与恢复处理
@admin_only
async def handle_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id):
        await update.message.reply_text(get_text("no_permission"))
        return
    await set_forward_paused(True)
    await update.message.reply_text(get_text("queue_paused"), parse_mode="Markdown")


@admin_only
async def handle_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_global_admin(update.message.from_user.id):
        await update.message.reply_text(get_text("no_permission"))
        return

    await set_forward_paused(False)
    await update.message.reply_text(get_text("queue_resumed"), parse_mode="Markdown")

    # 尝试唤醒 Worker
    if await peek_forward_queue():
        if not context.job_queue.get_jobs_by_name("forward_worker"):
            context.job_queue.run_once(forward_worker, 1, name="forward_worker")