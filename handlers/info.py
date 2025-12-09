# handlers/info.py
# 信息查询命令：列表、详情、统计、帮助

import sqlite3
from telegram import Update
from telegram.ext import ContextTypes
from db import (
    DB_FILE,
    get_rules,
    get_footer,
    get_replacements,
    get_stats,
    get_chat_whitelist,
    get_quiet_mode,
    is_voting_enabled,
    get_triggers
)
from handlers.utils import is_global_admin, is_admin, check_chat_permission, escape_markdown


async def handle_listchats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT chat_id, title FROM chats ORDER BY chat_id")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await msg.reply_text("📭 当前没有记录任何频道或群组。")
        return

    uid = msg.from_user.id
    allowed_chats = []

    if is_global_admin(uid):
        allowed_chats = rows
    else:
        status_msg = await msg.reply_text("⏳ 正在检查权限...")
        for chat_id, title in rows:
            if await check_chat_permission(uid, chat_id, context):
                allowed_chats.append((chat_id, title))
        await status_msg.delete()

    if not allowed_chats:
        await msg.reply_text("📭 你当前没有管理任何 Bot 所在的频道/群组。")
        return

    reply = "📋 *可管理的频道/群组列表*：\n\n"
    for chat_id, title in allowed_chats:
        safe_title = escape_markdown(title or "(无名称)")
        reply += f"• `{chat_id}` → {safe_title}\n"
    await msg.reply_text(reply.strip(), parse_mode="Markdown")


async def handle_chatinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()

    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限查看该频道信息。")
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT title FROM chats WHERE chat_id=?", (chat_id,))
        r = c.fetchone()
        title = r[0] if r else "未记录"
        conn.close()

        rules = get_rules(chat_id)
        footer = get_footer(chat_id)
        replacements = get_replacements(chat_id)
        whitelisted_users = get_chat_whitelist(chat_id)
        quiet_mode = get_quiet_mode(chat_id)
        voting_on = is_voting_enabled(chat_id)
        triggers = get_triggers(chat_id)

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

        await msg.reply_text(f"📍 *频道信息*\n\n🆔 ID：`{chat_id}`\n📛 名称：{safe_title}\n{details}", parse_mode="Markdown")
    else:
        await msg.reply_text("❌ 用法：/chatinfo -100频道ID")


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return

    rows = get_stats()
    uid = msg.from_user.id
    allowed_rows = []

    if is_global_admin(uid):
        allowed_rows = rows
    else:
        status_msg = await msg.reply_text("⏳ 正在获取统计数据...")
        for cid, count in rows:
            if await check_chat_permission(uid, cid, context):
                allowed_rows.append((cid, count))
        await status_msg.delete()

    if not allowed_rows:
        await msg.reply_text("📭 暂无数据")
        return

    reply = "📊 *清理统计*：\n\n" + "\n".join(f"• `{cid}` → {count} 次" for cid, count in allowed_rows)
    await msg.reply_text(reply.strip(), parse_mode="Markdown")


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg):
        return

    is_global = is_global_admin(msg.from_user.id)
    role = "固定管理员 (Super Admin)" if is_global else "频道管理员 (Chat Admin)"
    target_hint = " -100频道ID"

    help_text = f"""
🤖 *Jaikcl_Bot 使用手册*
👤 当前权限：`{role}`

💡 *提示*：点击命令可复制，`{target_hint}` 需替换为真实ID。

━━━━━━━━━━━━━━━━━━
🛠 **内容增强 (Content)**
*🔑 关键词屏蔽* (支持批量)
`/addkw`{target_hint} `词1 词2 ... [regex]` — ➕ 添加(批量)
`/addkw all 词1 词2 ...` — 🌐 **全群添加** (仅超管)
`/delkw`{target_hint} `词` — ➖ 删除屏蔽
`/listkw`{target_hint} — 📜 屏蔽列表

*🔄 关键词替换*
`/addreplace`{target_hint} `旧 新` — ➕ 替换
`/delreplace`{target_hint} `旧` — ➖ 删除替换
`/listreplace`{target_hint} — 📜 替换列表

*📝 页脚 & 白名单*
`/setfooter`{target_hint} `内容` — 📝 设置页脚
`/delfooter`{target_hint} — 🗑 删除页脚
`/allowuser`{target_hint} `ID` — 🛡 加白名单
`/blockuser`{target_hint} `ID` — 🚫 移出白名单
`/listallowed`{target_hint} — 📜 查看白名单

━━━━━━━━━━━━━━━━━━
🧩 **规则配置 (Rules)**
`/setrules`{target_hint} `规则...` — ⚡️ 覆盖设置
`/addrule`{target_hint} `规则` — ➕ 添加规则
`/delrule`{target_hint} `规则` — ➖ 删除规则
`/clearrules`{target_hint} — 🗑 清空规则
`/listrules`{target_hint} — 📜 查看规则

*📝 规则参数说明*：
`clean_keywords`: *温和屏蔽* (仅删含关键词的行)
`block_keywords`: *严格屏蔽* (含关键词删整条)
`strip_all_if_links`: *严格删链* (含链接删整条)
`clean_links`: *智能删链* (去链接留文字)
`remove_at_prefix`: 删除 @引用
`keep_all`: 不清理
`maxlen:50`: 长度限制

━━━━━━━━━━━━━━━━━━
🎮 **控制与回复**
`/setquiet`{target_hint} `[off/quiet/autodel]` — 🔕 回复模式
`/setvoting`{target_hint} `[on/off]` — 👍 互动投票
`/lock`{target_hint} — 🔒 锁定(暂停)
`/unlock`{target_hint} — 🔓 解锁(恢复)

*🤖 关键词自动回复*
`/addtrigger`{target_hint} `词 内容` — 添加
`/deltrigger`{target_hint} `词` — 删除
`/listtriggers`{target_hint} — 列表

━━━━━━━━━━━━━━━━━━
📊 **查询与监控**
`/listchats` — 📋 管理列表
`/chatinfo`{target_hint} — 📍 详细配置
`/stats` — 📈 统计数据
`/preview`{target_hint} `文本` — 👁‍🗨 模拟预览

━━━━━━━━━━━━━━━━━━
🔁 **转发设置**
`/addforward` -100源 -100目标 — ✅ 加转发
`/delforward` -100源 -100目标 — ❌ 删转发
`/listforward` -100源 — 📋 看转发

━━━━━━━━━━━━━━━━━━
"""
    if is_global:
        help_text += f"""⚙️ *系统管理 (超管)*
`/setlog`{target_hint} — 📝 日志频道
`/dellog` — 📴 关闭日志
`/setlogfilter` — ⚖️ 日志过滤
`/cleanchats` — 🧹 清理无效群
`/cleandb` — 💾 维护数据库
`/leave`{target_hint} — 👋 强制退群
`/addadmin ID` — ➕ 动态管理员
`/deladmin ID` — ➖ 删除管理员
`/listadmins` — 👑 管理员列表
`/backupdb` — 📦 备份
`/restoredb` — 📥 恢复
"""
    await msg.reply_text(help_text.strip(), parse_mode="Markdown")