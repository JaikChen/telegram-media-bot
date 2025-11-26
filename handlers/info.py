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
    is_voting_enabled
)
from handlers.utils import is_global_admin, is_admin, check_chat_permission


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
        status_msg = await msg.reply_text("⏳ 正在检查权限，请稍候...")
        for chat_id, title in rows:
            if await check_chat_permission(uid, chat_id, context):
                allowed_chats.append((chat_id, title))
        await status_msg.delete()

    if not allowed_chats:
        await msg.reply_text("📭 你当前没有管理任何 Bot 所在的频道/群组。")
        return

    reply = "📋 *可管理的频道/群组列表*：\n\n"
    for chat_id, title in allowed_chats:
        name = title.strip() if title else "(无名称)"
        reply += f"• `{chat_id}` → {name}\n"
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

        title = "(未记录名称)"
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT title FROM chats WHERE chat_id=?", (chat_id,))
        r = c.fetchone()
        if r: title = r[0]
        conn.close()

        # 获取各项配置
        rules = get_rules(chat_id)
        footer = get_footer(chat_id)
        replacements = get_replacements(chat_id)
        whitelisted_users = get_chat_whitelist(chat_id)
        quiet_mode = get_quiet_mode(chat_id)
        voting_on = is_voting_enabled(chat_id)

        # 状态格式化
        q_map = {"off": "🔔 正常回复", "quiet": "🔕 完全静音", "autodel": "🔥 阅后即焚"}
        q_status = q_map.get(quiet_mode, "🔔 正常回复")
        v_status = "✅ 开启" if voting_on else "🚫 关闭"

        details = f"• 规则：`{', '.join(rules) or '(未设置)'}`\n"
        details += f"• 模式：{q_status}\n"
        details += f"• 投票：{v_status}\n"
        details += f"• 页脚：{'✅ 已设置' if footer else '(无)'}\n"
        details += f"• 替换：{len(replacements)} 个\n"
        details += f"• 白名单：{len(whitelisted_users)} 人"

        await msg.reply_text(f"📍 *频道信息*\n\n🆔 ID：`{chat_id}`\n📛 名称：{title}\n{details}", parse_mode="Markdown")
    else:
        await msg.reply_text("❌ 用法错误：/chatinfo -100频道ID")


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return

    rows = get_stats()
    if not rows:
        await msg.reply_text("📭 暂无清理记录。")
        return

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
        await msg.reply_text("📭 你管理的频道暂无清理记录。")
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
🤖 *Jaikcl_Bot 全能管理指南*
👤 当前身份：`{role}`

💡 *提示*：点击命令即可复制，请将 `{target_hint}` 替换为真实ID。

━━━━━━━━━━━━━━━━━━
🧩 *规则配置 (Rules)*
`/setrules`{target_hint} `规则...` — ⚡️ 覆盖设置所有规则
`/addrule`{target_hint} `规则` — ➕ 添加单条规则
`/delrule`{target_hint} `规则` — ➖ 删除单条规则
`/clearrules`{target_hint} — 🗑 清空所有规则
`/listrules`{target_hint} — 📜 查看规则列表

📝 *规则参数说明*：
`keep_all`: 保留所有(不清理)
`strip_all_if_links`: 若含链接(含文字链)则删除整条说明
`clean_links`: 仅剔除文本中的链接，保留其他文字
`remove_at_prefix`: 剔除 @开头的引用
`block_keywords`: 启用关键词/正则屏蔽
`maxlen:50`: 限制文字长度不超过50字

━━━━━━━━━━━━━━━━━━
🛠 *内容增强 (Content)*
*🔑 关键词屏蔽*
`/addkw`{target_hint} `词 [regex]` — 添加屏蔽词
`/delkw`{target_hint} `词` — 删除屏蔽词
`/listkw`{target_hint} — 查看屏蔽列表

*🔄 关键词替换*
`/addreplace`{target_hint} `旧词 新词` — 设置替换
`/delreplace`{target_hint} `旧词` — 删除替换
`/listreplace`{target_hint} — 查看替换列表

*📝 页脚 & 白名单*
`/setfooter`{target_hint} `内容` — 设置消息小尾巴
`/delfooter`{target_hint} — 删除页脚
`/allowuser`{target_hint} `用户ID` — 🛡 添加白名单(免清理)
`/blockuser`{target_hint} `用户ID` — 移除白名单
`/listallowed`{target_hint} — 查看白名单

━━━━━━━━━━━━━━━━━━
🎮 *群组控制 (Control)*
`/setquiet`{target_hint} `[off/quiet/autodel]` — 🔕 设置Bot回复模式
`/setvoting`{target_hint} `[on/off]` — 👍 开启/关闭互动投票
`/lock`{target_hint} — 🔒 锁定频道(暂停Bot)
`/unlock`{target_hint} — 🔓 解锁频道
`/preview`{target_hint} `文本` — 👁‍🗨 模拟清理预览

━━━━━━━━━━━━━━━━━━
📊 *查询统计 (Query)*
`/listchats` — 📋 查看我管理的频道列表
`/chatinfo`{target_hint} — 📍 查看频道详细配置
`/stats` — 📈 查看清理次数统计

━━━━━━━━━━━━━━━━━━
🔁 *转发设置 (Forward)*
`/addforward` -100源 -100目标 — ✅ 添加转发关系
`/delforward` -100源 -100目标 — ❌ 删除转发关系
`/listforward` -100源 — 📋 查看转发目标

━━━━━━━━━━━━━━━━━━
"""

    # 仅固定管理员可见的系统命令
    if is_global:
        help_text += f"""⚙️ *系统管理 (Super Admin)*
`/setlog`{target_hint} — 📝 设置全局日志频道
`/dellog` — 📴 关闭日志记录
`/cleanchats` — 🧹 清理无效/解散群组数据
`/cleandb` — 💾 立即清理过期数据(1年)
`/leave`{target_hint} — 👋 强制 Bot 退出群组
`/addadmin 用户ID` — ➕ 添加动态管理员
`/deladmin 用户ID` — ➖ 删除动态管理员
`/listadmins` — 👑 查看所有管理员
`/backupdb` — 📦 备份数据库
`/restoredb` — 📥 恢复数据库(需回复文件)
"""

    await msg.reply_text(help_text.strip(), parse_mode="Markdown")