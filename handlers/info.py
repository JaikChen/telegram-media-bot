# handlers/info.py
# 信息查询命令：列表、详情、统计、帮助

import sqlite3
from telegram import Update
from telegram.ext import ContextTypes
from db import DB_FILE, get_rules, get_footer, get_replacements, get_stats, get_chat_whitelist
from handlers.utils import is_global_admin, is_admin, check_chat_permission


async def handle_listchats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    conn = sqlite3.connect(DB_FILE);
    c = conn.cursor()
    c.execute("SELECT chat_id, title FROM chats ORDER BY chat_id")
    rows = c.fetchall();
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
    reply = "📋 **可管理的频道/群组列表**：\n\n"
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
        conn = sqlite3.connect(DB_FILE);
        c = conn.cursor()
        c.execute("SELECT title FROM chats WHERE chat_id=?", (chat_id,))
        r = c.fetchone()
        if r: title = r[0]
        rules = get_rules(chat_id)
        footer = get_footer(chat_id)
        replacements = get_replacements(chat_id)
        whitelisted_users = get_chat_whitelist(chat_id)

        details = f"• 规则：`{', '.join(rules) or '(未设置)'}`\n"
        details += f"• 页脚：{'✅ 已设置' if footer else '(无)'}\n"
        details += f"• 替换词：{len(replacements)} 个\n"
        details += f"• 白名单用户：{len(whitelisted_users)} 人"

        await msg.reply_text(f"📍 **频道信息**：\n\n🆔 ID：`{chat_id}`\nYs 名称：{title}\n{details}", parse_mode="Markdown")
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
    reply = "📊 **清理统计**：\n\n" + "\n".join(f"• `{cid}` → {count} 次" for cid, count in allowed_rows)
    await msg.reply_text(reply.strip(), parse_mode="Markdown")


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg):
        return

    is_global = is_global_admin(msg.from_user.id)
    role = "固定管理员 (Super Admin)" if is_global else "动态管理员 (Chat Admin)"
    extra_note = " *(仅限你管理的频道)*" if not is_global else ""

    help_text = f"""
🤖 *Jaikcl_Bot 管理命令帮助*
👤 身份：`{role}`

📌 *说明*：频道 ID 请使用 `-100` 开头的完整 ID。点击命令可复制。

━━━━━━━━━━━━━━━━━━
🧩 **基础规则管理**{extra_note}
`/setrules -100xxx 规则1,规则2` — 覆盖设置规则
`/addrule -100xxx 规则` — 添加单条规则
`/delrule -100xxx 规则` — 删除单条规则
`/listrules -100xxx` — 查看规则列表
`/clearrules -100xxx` — 清空所有规则

📖 *可用规则*：
`keep_all` (保留所有), `strip_all_if_links` (含链接则整条删除), `clean_links` (仅删链接), `remove_at_prefix` (删@前缀), `block_keywords` (启用关键词屏蔽), `maxlen:50` (限长50字)

━━━━━━━━━━━━━━━━━━
🛠 **内容处理增强**{extra_note}
*🔑 关键词屏蔽*
`/addkw -100xxx 词 [regex]` — 添加屏蔽词(支持正则)
`/delkw -100xxx 词` — 删除屏蔽词
`/listkw -100xxx` — 查看屏蔽列表

*🔄 关键词替换*
`/addreplace -100xxx 旧词 新词` — 将旧词替换为新词
`/delreplace -100xxx 旧词` — 删除替换规则
`/listreplace -100xxx` — 查看替换列表

*📝 自定义页脚*
`/setfooter -100xxx 内容` — 设置清理后的消息页脚
`/delfooter -100xxx` — 删除页脚

*🛡 用户白名单* (免除清理)
`/allowuser -100xxx 用户ID` — 添加白名单用户
`/blockuser -100xxx 用户ID` — 移出白名单
`/listallowed -100xxx` — 查看白名单列表

━━━━━━━━━━━━━━━━━━
🎮 **控制与统计**
`/lock -100xxx` — 🔒 锁定频道(暂停清理)
`/unlock -100xxx` — 🔓 解锁频道
`/stats` — 📊 查看清理统计
`/listchats` — 📋 查看频道列表
`/chatinfo -100xxx` — 📍 查看频道详情
`/preview -100xxx 文本` — 🧹 模拟清理预览结果

━━━━━━━━━━━━━━━━━━
🔁 **转发映射**{extra_note}
`/addforward -100源ID -100目标ID` — 添加转发关系
`/delforward -100源ID -100目标ID` — 删除转发关系
`/listforward -100源ID` — 查看转发目标

━━━━━━━━━━━━━━━━━━
"""

    # 仅固定管理员可见的系统命令部分
    if is_global:
        help_text += """⚙️ **系统管理 (仅固定管理员)**
`/setlog -100xxx` — 设置全局日志频道
`/dellog` — 关闭日志记录
`/cleanchats` — 🧹 清理数据库中无效/被踢的群组
`/leave -100xxx` — 👋 强制 Bot 退出群组
`/addadmin 用户ID` — 添加动态管理员
`/deladmin 用户ID` — 删除动态管理员
`/listadmins` — 查看所有管理员
`/backupdb` — 💾 备份数据库
`/restoredb` — 📥 恢复数据库(需回复文件)
"""

    await msg.reply_text(help_text.strip(), parse_mode="Markdown")