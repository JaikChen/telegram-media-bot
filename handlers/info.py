# handlers/info.py
from telegram import Update
from telegram.ext import ContextTypes
from db import (
    get_rules, get_footer, get_replacements, get_stats,
    get_chat_whitelist, get_quiet_mode, is_voting_enabled,
    get_triggers, get_delay_settings, execute_sql
)
from handlers.utils import admin_only, is_global_admin, check_chat_permission, escape_markdown
from locales import get_text


@admin_only
async def handle_listchats(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


@admin_only
async def handle_chatinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ 用法：`/chatinfo -100xxx`", parse_mode="Markdown")
        return

    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    r = await execute_sql("SELECT title FROM chats WHERE chat_id=?", (chat_id,), fetchone=True)
    title = r[0] if r else "未记录"

    rules = await get_rules(chat_id)
    footer = await get_footer(chat_id)
    replacements = await get_replacements(chat_id)
    whitelisted_users = await get_chat_whitelist(chat_id)
    quiet_mode = await get_quiet_mode(chat_id)
    voting_on = await is_voting_enabled(chat_id)
    triggers = await get_triggers(chat_id)

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

    await update.message.reply_text(f"📍 *频道信息*\n\n🆔 ID：`{chat_id}`\n📛 名称：{safe_title}\n{details}",
                                    parse_mode="Markdown")


@admin_only
async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await get_stats()
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


@admin_only
async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_global = is_global_admin(update.message.from_user.id)
    role = "固定管理员 (Super Admin)" if is_global else "频道管理员 (Chat Admin)"
    target_hint = " -100频道ID"
    min_s, max_s = await get_delay_settings()
    delay_status = f"{min_s}~{max_s}秒" if max_s > 0 else "关闭(实时)"

    # 基础帮助内容
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

*🌫 自动防剧透*
发送媒体说明中包含 `#spoiler` / `#剧透` / `#nsfw` 即可自动打码。

━━━━━━━━━━━━━━━━━━
🔁 **转发设置**
`/addforward` -100源 -100目标 — ✅ 建立转发
`/delforward` -100源 -100目标 — ❌ 解除转发
`/listforward` -100源 — 📋 查看转发链

━━━━━━━━━━━━━━━━━━
"""
    # 超级管理员专属菜单
    if is_global:
        help_text += f"""⚙️ *系统管理 (Super Admin)*
`/setdelay min max` — ⏱ **设置转发延迟(秒)**
`/setlog`{target_hint} — 📝 设置日志频道
`/setlogfilter` — ⚖️ 过滤日志类型
`/dellog` — 📴 关闭日志
`/cleanchats` — 🧹 清理无效群组数据
`/cleandb` — 💾 数据库维护(VACUUM)
`/leave`{target_hint} — 👋 强制退群
`/addadmin ID` — ➕ 添加动态管理员
`/deladmin ID` — ➖ 删除动态管理员
`/listadmins` — 👑 管理员列表
`/backupdb` — 📦 备份数据库
`/restoredb` — 📥 恢复数据库
"""
    await update.message.reply_text(help_text.strip(), parse_mode="Markdown")