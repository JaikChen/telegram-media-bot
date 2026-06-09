# handlers/sys_admin.py
"""
System administration handlers for global bot management.
Includes admin management, database maintenance, logging configuration, and queue control.
"""

import os
import logging
import io
import time
from datetime import datetime

from telegram import Update, InputFile
from telegram.ext import ContextTypes
from telegram.error import BadRequest, Forbidden

from src.bot.core.config import ADMIN_IDS, DB_FILE
from src.bot.data.repositories import AdminRepository, ChatRepository, MediaRepository, execute_sql
from src.bot.utils.helpers import is_global_admin, log_event, escape_markdown, admin_only
from src.bot.core.locales import get_text
from src.bot.domain.forwarding import ForwardingService

logger = logging.getLogger(__name__)


@admin_only
async def handle_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a dynamic administrator to the database (Global Admin only)."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    if len(context.args or []) < 1:
        await update.message.reply_text(get_text("args_error"))
        return

    try:
        new_admin_id = context.args[0]
        await AdminRepository.add_admin(new_admin_id)
        await update.message.reply_text(get_text("admin_added", new_admin_id))
        await log_event(context.bot, f"添加管理员: {new_admin_id}", category="system")
        logger.info(f"Admin added: {new_admin_id} by {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in handle_addadmin: {e}")


@admin_only
async def handle_deladmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a dynamic administrator from the database (Global Admin only)."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    if len(context.args or []) < 1:
        await update.message.reply_text(get_text("args_error"))
        return

    try:
        admin_id = context.args[0]
        await AdminRepository.delete_admin(admin_id)
        await update.message.reply_text(get_text("admin_deleted", admin_id))
        await log_event(context.bot, f"移除管理员: {admin_id}", category="system")
        logger.info(f"Admin removed: {admin_id} by {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in handle_deladmin: {e}")


@admin_only
async def handle_listadmins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all administrators, both fixed (from config) and dynamic (from DB)."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    try:
        admins = await AdminRepository.list_admins()
        fixed = sorted(ADMIN_IDS)
        reply = "👑 管理员列表：\n\n• 固定：\n" + "\n".join(f" - {a}" for a in fixed)
        reply += "\n\n• 动态：\n" + ("\n".join(f" - {a}" for a in admins) if admins else " - (空)")
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Error in handle_listadmins: {e}")


@admin_only
async def handle_backupdb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the database file to the global admin for backup."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    try:
        if not os.path.exists(DB_FILE):
            await update.message.reply_text("❌ 无数据库")
            return

        with open(DB_FILE, "rb") as db_file:
            await context.bot.send_document(
                chat_id=update.message.chat_id,
                document=InputFile(db_file, filename=os.path.basename(DB_FILE)),
                caption=get_text("backup_caption"),
            )
        await log_event(context.bot, "管理员执行了数据库备份", category="system")
        logger.info(f"Database backup performed by {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in handle_backupdb: {e}")


@admin_only
async def handle_restoredb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Restore the database by uploading a backup file (replies required)."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    msg = update.message
    if not msg.reply_to_message or not msg.reply_to_message.document:
        await msg.reply_text("❌ 请回复包含数据库备份文件的消息")
        return

    try:
        doc = msg.reply_to_message.document
        file = await context.bot.get_file(doc.file_id)

        tmp = io.BytesIO()
        await file.download_to_memory(out=tmp)
        tmp.seek(0)

        # Overwrite database file
        with open(DB_FILE, "wb") as f:
            f.write(tmp.read())

        await msg.reply_text(get_text("restore_success"))
        await log_event(context.bot, "管理员执行了数据库恢复", category="system")
        logger.warning(f"Database RESTORE performed by {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in handle_restoredb: {e}")
        await msg.reply_text(f"❌ 恢复失败: {e}")


@admin_only
async def handle_setlog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Configure the Telegram channel for event logging."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    if len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法：`/setlog -100xxx`", parse_mode="Markdown")
        return

    try:
        log_cid = context.args[0]
        await MediaRepository.set_log_channel_global(log_cid)
        await update.message.reply_text(get_text("log_set", log_cid), parse_mode="Markdown")
        try:
            await context.bot.send_message(log_cid, "📡 测试消息：日志频道已成功关联。")
        except Exception as e:
            await update.message.reply_text(f"⚠️ 无法发送测试消息到 {log_cid}: {e}")
        logger.info(f"Log channel set to {log_cid} by {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in handle_setlog: {e}")


@admin_only
async def handle_dellog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disable event logging to Telegram."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    try:
        await MediaRepository.set_log_channel_global("")
        await update.message.reply_text(get_text("log_off"))
        logger.info(f"Log channel disabled by {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in handle_dellog: {e}")


@admin_only
async def handle_setlogfilter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set which categories of events should be logged to the log channel."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    valid_types = ["clean", "duplicate", "forward", "error", "system"]

    try:
        if len(context.args or []) < 1:
            current = await ChatRepository.get_log_filter(str(update.effective_chat.id))
            await update.message.reply_text(
                f"📝 当前日志过滤：\n`{', '.join(current)}`\n\n可用类型：`{' '.join(valid_types)}`",
                parse_mode="Markdown",
            )
            return

        new_types = [t for t in context.args if t in valid_types]
        if not new_types:
            await update.message.reply_text(get_text("args_error"), parse_mode="Markdown")
            return

        await ChatRepository.set_log_filter(str(update.effective_chat.id), new_types)
        await update.message.reply_text(f"✅ 日志过滤已更新：\n`{', '.join(new_types)}`", parse_mode="Markdown")
        logger.info(f"Log filters updated to {new_types} by {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in handle_setlogfilter: {e}")


@admin_only
async def handle_cleanchats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Identify and remove chats where the bot is no longer a member."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    try:
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
                await execute_sql("DELETE FROM chats WHERE chat_id=?", (cid,), commit=True)
                count += 1
                safe_title = escape_markdown(title or "未命名")
                details.append(f"`{cid}` {safe_title}")
            except Exception:
                pass

        if count > 0:
            await status_msg.edit_text(f"✅ 清理了 {count} 个无效群组：\n" + "\n".join(details), parse_mode="Markdown")
            await log_event(context.bot, f"清理了 {count} 个无效群组", category="system")
        else:
            await status_msg.edit_text("✅ 无无效群组")
        logger.info(f"Clean chats: removed {count} invalid chats")
    except Exception as e:
        logger.error(f"Error in handle_cleanchats: {e}")


@admin_only
async def handle_cleandb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Perform database maintenance: clear expired records and vacuum."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    try:
        status_msg = await update.message.reply_text("⏳ 正在清理过期数据并整理数据库...")
        deleted = await MediaRepository.clean_expired_data(days=365)
        await MediaRepository.vacuum_db()
        await status_msg.edit_text(get_text("maintenance_complete", deleted))
        await log_event(context.bot, f"手动执行数据库维护，清理 {deleted} 条记录", category="system")
        logger.info(f"Database maintenance: cleaned {deleted} records")
    except Exception as e:
        logger.error(f"Error in handle_cleandb: {e}")


@admin_only
async def handle_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Force the bot to leave a specific chat."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    if len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法：`/leave -100xxx`", parse_mode="Markdown")
        return

    try:
        chat_id = context.args[0]
        await context.bot.leave_chat(chat_id)
        await update.message.reply_text(f"👋 已退出 `{chat_id}`", parse_mode="Markdown")
        await log_event(context.bot, f"强制退出群组: {chat_id}", category="system")
        logger.info(f"Bot forced to leave chat {chat_id} by {update.effective_user.id}")
    except Exception as e:
        await update.message.reply_text(f"❌ 失败: {e}")
        logger.error(f"Error in handle_leave: {e}")


@admin_only
async def handle_setdelay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Configure the random delay range for message forwarding."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    try:
        # No arguments: show current settings
        if len(context.args or []) == 0:
            min_s, max_s = await MediaRepository.get_delay_settings()
            if min_s == 0 and max_s == 0:
                await update.message.reply_text("⏱ 当前设置：**无延迟** (实时转发)", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"⏱ 当前设置：**{min_s} ~ {max_s} 秒** 随机延迟", parse_mode="Markdown")
            return

        # Set new range
        if len(context.args or []) == 2:
            try:
                min_s = int(context.args[0])
                max_s = int(context.args[1])
                if min_s < 0 or max_s < min_s:
                    raise ValueError

                await MediaRepository.set_delay_settings(min_s, max_s)

                if min_s == 0 and max_s == 0:
                    await update.message.reply_text("✅ 已关闭延迟，恢复实时转发。")
                else:
                    await update.message.reply_text(
                        f"✅ 已设置转发延迟：**{min_s} ~ {max_s} 秒**", parse_mode="Markdown"
                    )
                    await log_event(context.bot, f"更新转发延迟为 {min_s}-{max_s}s", category="system")
                logger.info(f"Forward delay set to {min_s}-{max_s}s by {update.effective_user.id}")
            except ValueError:
                await update.message.reply_text(
                    "❌ 错误：请输入有效的整数，且 min <= max。\n示例：`/setdelay 60 120`", parse_mode="Markdown"
                )
        else:
            await update.message.reply_text("❌ 用法：`/setdelay min max` (单位秒，0 0 关闭)", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in handle_setdelay: {e}")


@admin_only
async def handle_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Globally pause the forwarding queue."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    try:
        await MediaRepository.set_forward_paused(True)
        await update.message.reply_text(get_text("queue_paused"), parse_mode="Markdown")
        logger.info(f"Forwarding PAUSED by {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in handle_pause: {e}")


@admin_only
async def handle_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Globally resume the forwarding queue and wake the worker."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    try:
        await MediaRepository.set_forward_paused(False)
        await update.message.reply_text(get_text("queue_resumed"), parse_mode="Markdown")
        logger.info(f"Forwarding RESUMED by {update.effective_user.id}")

        # Wake worker if there are pending tasks
        if await MediaRepository.peek_queue():
            if not context.job_queue.get_jobs_by_name("forward_worker"):
                context.job_queue.run_once(ForwardingService.forward_worker, 1, name="forward_worker")
    except Exception as e:
        logger.error(f"Error in handle_resume: {e}")


@admin_only
async def handle_dlq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View the most recent failed tasks in the Dead Letter Queue."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    try:
        rows = await execute_sql(
            "SELECT id, target_chat_id, media_type, reason, failed_at FROM dead_letter_queue ORDER BY id DESC LIMIT 10",
            fetchall=True,
        )
        if not rows:
            await update.message.reply_text("✅ 死信队列为空。")
            return

        reply = "💀 **最近失败任务 (DLQ):**\n\n"
        for r_id, tid, m_type, reason, ts in rows:
            t_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
            reply += f"ID: `{r_id}` | 目标: `{tid}` | 类型: `{m_type}`\n原因: `{reason}` | 时间: `{t_str}`\n\n"
        reply += "使用 `/retrydlq {id|all}` 重试，`/cleardlq` 清空。"
        await update.message.reply_text(reply, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in handle_dlq: {e}")


@admin_only
async def handle_retry_dlq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retry failed tasks from the Dead Letter Queue."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    if not context.args:
        await update.message.reply_text("❌ 用法: `/retrydlq {id|all}`")
        return

    try:
        arg = context.args[0]
        if arg.lower() == "all":
            rows = await execute_sql("SELECT * FROM dead_letter_queue", fetchall=True)
            items = []
            for r in rows:
                # DLQ schema: id, target, type, fid, cap, sp, fuid, mgid, fail_ts, reason, scid, smid
                items.append(
                    {
                        "tid": r[1],
                        "mt": r[2],
                        "fid": r[3],
                        "cap": r[4],
                        "sp": bool(r[5]),
                        "fuid": r[6],
                        "mgid": r[7],
                        "prio": 1,
                        "scid": r[10],
                        "smid": r[11],
                    }
                )
            await MediaRepository.enqueue_batch(items)
            await execute_sql("DELETE FROM dead_letter_queue", commit=True)
            await update.message.reply_text(f"✅ 已将 {len(rows)} 条任务重新加入队列。")
        else:
            row = await execute_sql("SELECT * FROM dead_letter_queue WHERE id=?", (arg,), fetchone=True)
            if row:
                item = {
                    "tid": row[1],
                    "mt": row[2],
                    "fid": row[3],
                    "cap": row[4],
                    "sp": bool(row[5]),
                    "fuid": row[6],
                    "mgid": row[7],
                    "prio": 1,
                    "scid": row[10],
                    "smid": row[11],
                }
                await MediaRepository.enqueue_batch([item])
                await execute_sql("DELETE FROM dead_letter_queue WHERE id=?", (arg,), commit=True)
                await update.message.reply_text(f"✅ 任务 {arg} 已重试。")
            else:
                await update.message.reply_text("❌ 未找到该任务。")

        if not context.job_queue.get_jobs_by_name("forward_worker"):
            context.job_queue.run_once(ForwardingService.forward_worker, 1, name="forward_worker")
    except Exception as e:
        logger.error(f"Error in handle_retry_dlq: {e}")


@admin_only
async def handle_clear_dlq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all tasks from the Dead Letter Queue."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        return

    try:
        await execute_sql("DELETE FROM dead_letter_queue", commit=True)
        await update.message.reply_text("🗑 死信队列已清空。")
        logger.info(f"DLQ cleared by {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in handle_clear_dlq: {e}")


@admin_only
async def handle_repair_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually restart the forwarding worker if it hangs and reset all processing states."""
    if not update.message or not is_global_admin(update.message.from_user.id):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        if await MediaRepository.is_forward_paused():
            await update.message.reply_text("⚠️ 队列当前处于暂停状态，请先使用 /resume 恢复。")
            return

        # Reset all "processing" status to "waiting"
        await execute_sql("UPDATE forward_queue SET status = 0, updated_at = ?", (int(time.time()),), commit=True)

        if await MediaRepository.peek_queue():
            # Clear existing jobs to avoid duplicates
            jobs = context.job_queue.get_jobs_by_name("forward_worker")
            for j in jobs:
                j.schedule_removal()

            context.job_queue.run_once(ForwardingService.forward_worker, 1, name="forward_worker")
            await update.message.reply_text("🔄 已重置队列状态并尝试手动唤醒转发工人。")
            await log_event(
                context.bot, f"管理员 {update.effective_user.id} 执行了队列修复 (/repair)", category="system"
            )
        else:
            await update.message.reply_text("✅ 转发队列当前为空，无需修复。")
    except Exception as e:
        logger.error(f"Error in handle_repair_queue: {e}")
        await update.message.reply_text(f"❌ 修复失败: {e}")
