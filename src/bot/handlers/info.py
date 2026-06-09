# handlers/info.py
"""
Information and help handlers for querying bot status, chat configurations, and statistics.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.data.repositories import MediaRepository, ChatRepository, VoteRepository, execute_sql
from src.bot.utils.helpers import admin_only, is_global_admin, escape_markdown, check_chat_permission
from src.bot.core.locales import get_text

logger = logging.getLogger(__name__)


@admin_only
async def handle_listchats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all chats managed by the bot that the user has permission to view."""
    if not update.message:
        return

    try:
        rows = await execute_sql("SELECT chat_id, title FROM chats ORDER BY chat_id", fetchall=True)
        if not rows:
            await update.message.reply_text(get_text("no_data"))
            return

        uid = update.message.from_user.id
        allowed_chats = []

        if is_global_admin(uid):
            allowed_chats = rows
        else:
            status_msg = await update.message.reply_text("⏳ 正在检查权限...")
            for chat_id, title in rows:
                if await check_chat_permission(uid, chat_id, context):
                    allowed_chats.append((chat_id, title))
            await status_msg.delete()

        if not allowed_chats:
            await update.message.reply_text("📭 你当前没有管理任何 Bot 所在的频道/群组。")
            return

        reply = "📋 *可管理的频道/群组列表*：\n\n"
        for chat_id, title in allowed_chats:
            safe_title = escape_markdown(title or "(无名称)")
            reply += f"• `{chat_id}` → {safe_title}\n"
        await update.message.reply_text(reply.strip(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in handle_listchats: {e}")


@admin_only
async def handle_chatinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display detailed configuration information for a specific chat."""
    if not update.message or len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法：`/chatinfo -100xxx`", parse_mode="Markdown")
        return

    chat_id = context.args[0]
    try:
        if not await check_chat_permission(update.message.from_user.id, chat_id, context):
            await update.message.reply_text(get_text("no_permission"))
            return

        r = await execute_sql("SELECT title FROM chats WHERE chat_id=?", (chat_id,), fetchone=True)
        title = r[0] if r else "未记录"

        rules = await ChatRepository.get_chat_rules(chat_id)
        footer = await ChatRepository.get_footer(chat_id)
        replacements = await ChatRepository.get_replacements(chat_id)
        whitelisted_users = await ChatRepository.get_chat_whitelist(chat_id)
        quiet_mode = await ChatRepository.get_quiet_mode(chat_id)
        voting_on = await VoteRepository.is_voting_enabled(chat_id)
        triggers = await ChatRepository.get_triggers(chat_id)

        q_map = {"off": "🔔 正常", "quiet": "🔕 静音", "autodel": "🔥 阅后即焚"}
        q_status = q_map.get(quiet_mode, "🔔 正常")
        v_status = "✅ 开启" if voting_on else "🚫 关闭"
        safe_title = escape_markdown(title)

        details = f"• 规则：`{', '.join(rules) or '(未设置)'}`\n"
        details += f"• 模式：{q_status}\n"
        details += f"• 投票：{v_status}\n"
        details += f"• 页脚：{'✅ 已设' if footer else '(无)'}\n"
        details += f"• 替换：{len(replacements)} 个\n"
        details += f"• 触发器：{len(triggers)} 个\n"
        details += f"• 白名单：{len(whitelisted_users)} 人"

        await update.message.reply_text(
            f"📍 *频道信息*\n\n🆔 ID：`{chat_id}`\n📛 名称：{safe_title}\n{details}", parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in handle_chatinfo: {e}")


@admin_only
async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display message processing statistics for managed chats."""
    if not update.message:
        return

    try:
        rows = await MediaRepository.get_stats()
        uid = update.message.from_user.id
        allowed_rows = []

        if is_global_admin(uid):
            allowed_rows = rows
        else:
            status_msg = await update.message.reply_text("⏳ 正在获取统计数据...")
            for cid, count in rows:
                if await check_chat_permission(uid, cid, context):
                    allowed_rows.append((cid, count))
            await status_msg.delete()

        if not allowed_rows:
            await update.message.reply_text(get_text("no_data"))
            return

        reply = "📊 *清理统计*：\n\n" + "\n".join(f"• `{cid}` → {count} 次" for cid, count in allowed_rows)
        await update.message.reply_text(reply.strip(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in handle_stats: {e}")


@admin_only
async def handle_queue_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the status of the forwarding queue (Global Admin only)."""
    if not update.message:
        return

    try:
        if not is_global_admin(update.message.from_user.id):
            await update.message.reply_text(get_text("no_permission"))
            return

        rows = await MediaRepository.get_forward_queue_counts()
        if not rows:
            await update.message.reply_text(get_text("queue_empty"), parse_mode="Markdown")
            return

        text = get_text("queue_status_title") + "\n\n"
        for chat_id, title, count in rows:
            safe_title = escape_markdown(title or "未知频道")
            text += get_text("queue_row", chat_id, safe_title, count) + "\n"

        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in handle_queue_status: {e}")


@admin_only
async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the help manual with available commands and descriptions."""
    if not update.message:
        return

    try:
        is_global = is_global_admin(update.message.from_user.id)
        role = "固定管理员 (Super Admin)" if is_global else "频道管理员 (Chat Admin)"
        target_hint = " -100频道ID"
        min_s, max_s = await MediaRepository.get_delay_settings()
        delay_status = f"{min_s}~{max_s}秒" if max_s > 0 else "关闭(实时)"

        help_text = f"""
🤖 *Jaikcl_Bot 全能手册*
👤 身份：`{role}`
⏱ 全局延迟：`{delay_status}`

💡 *使用小贴士*：
1. 点击蓝色命令即可复制。
2. 将 `{target_hint}` 替换为真实的频道 ID。
3. 🔥 **超级管理员**可将 ID 填为 `all`，对**所有**已记录频道进行批量操作！

━━━━━━━━━━━━━━━━━━
🧩 **规则配置 (Rules)**
_(支持 `all` 批量操作)_
`/setrules`{target_hint} `规则...` — ⚡️ 覆盖设置
`/addrule`{target_hint} `规则` — ➕ 添加单条
`/delrule`{target_hint} `规则` — ➖ 删除单条
`/clearrules`{target_hint} — 🗑 清空规则
`/listrules`{target_hint} — 📜 查看规则

*📝 常用规则参数*：
`clean_keywords`: **温和屏蔽** (仅删含广告的行)
`block_keywords`: **严格屏蔽** (发现关键词删整条)
`clean_links`: **智能删链** (去链接但保留文字)
`strip_all_if_links`: **严格删链** (有链接则删整条)
`remove_at_prefix`: 删除 @引用
`pangu`: **排版美化** (中英文间加空格)
`keep_all`: 不做任何清理
`maxlen:50`: 限制长度

━━━━━━━━━━━━━━━━━━
🛠 **内容净化与增强**
_(支持 `all` 批量操作)_
`/addkw`{target_hint} `词1 词2 ...` — ➕ 批量添加屏蔽词
`/addkw`{target_hint} `... regex` — 🧩 启用正则模式
`/delkw`{target_hint} `词` — ➖ 删除屏蔽词
`/listkw`{target_hint} — 📜 查看列表

*🔄 替换 & 页脚 & 白名单*
`/addreplace`{target_hint} `旧 新` — ➕ 文本替换
`/delreplace`{target_hint} `旧` — ➖ 删除替换
`/setfooter`{target_hint} `内容` — 📝 设置小尾巴
`/delfooter`{target_hint} — 🗑 删除页脚
`/allowuser`{target_hint} `ID` — 🛡 用户白名单(免清理)
`/blockuser`{target_hint} `ID` — 🚫 移出白名单

━━━━━━━━━━━━━━━━━━
🎮 **控制与交互**
`/setquiet`{target_hint} `[off/quiet/autodel]` — 🔕 回复模式
`/setvoting`{target_hint} `[on/off]` — 👍 互动投票开关
`/lock`{target_hint} — 🔒 锁定(暂停Bot)
`/unlock`{target_hint} — 🔓 解锁(恢复)

*🤖 关键词自动回复*
`/addtrigger`{target_hint} `词 内容` — 添加
`/deltrigger`{target_hint} `词` — 删除
`/listtriggers`{target_hint} — 列表

━━━━━━━━━━━━━━━━━━
🔁 **转发设置**
`/addforward` -100源 -100目标 — ✅ 建立转发
`/delforward` -100源 -100目标 — ❌ 解除转发
`/listforward` -100源 — 📋 查看转发链
`/listall` — 📋 **一键查询所有转发链**
`/queue` — 📊 **查看积压队列** (实时监控)

━━━━━━━━━━━━━━━━━━
"""
        if is_global:
            help_text += f"""⚙️ *系统管理 (Super Admin)*
`/pause` — ⏸ **暂停转发** (积压保留)
`/resume` — ▶️ **恢复转发** (处理积压)
`/setdelay min max` — ⏱ **设置延迟(秒)**
`/setlog`{target_hint} — 📝 设置日志频道
`/setlogfilter` — ⚖️ 过滤日志
`/cleanchats` — 🧹 清理无效群组
`/cleandb` — 💾 数据库维护
`/leave`{target_hint} — 👋 强制退群
`/addadmin ID` — ➕ 添加动态管理员
`/deladmin ID` — ➖ 删除动态管理员
`/listadmins` — 👑 管理员列表
`/backupdb` — 📦 备份数据库
`/restoredb` — 📥 恢复数据库
`/dlq` — 💀 查看死信队列
"""
        await update.message.reply_text(help_text.strip(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in handle_help: {e}")
