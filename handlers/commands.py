# handlers/commands.py
# 管理命令：规则、关键词、管理员、转发映射、替换词、页脚、退出群组、日志频道等

from telegram import Update, InputFile
from telegram.ext import ContextTypes
from telegram.error import BadRequest, Forbidden
from config import ADMIN_IDS
from db import *
from cleaner import clean_caption
import os
import io


# =========================
# 权限辅助函数
# =========================

def is_global_admin(user_id: str | int) -> bool:
    """检查是否为固定配置的超级管理员"""
    return str(user_id) in ADMIN_IDS


async def is_admin(msg):
    uid = str(msg.from_user.id)
    if is_global_admin(uid):
        return True
    return uid in list_admins()


async def check_chat_permission(user_id: int | str, chat_id: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    uid = str(user_id)
    if is_global_admin(uid):
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception:
        return False


# ... (保留 setrules, addrule, delrule, listrules, clearrules, listchats, chatinfo, cleanchats, leave 等函数) ...
# 为了节省篇幅，这里略过中间未变动的代码，请保持原有的所有函数，并在末尾添加以下日志管理命令

# ... [保留前面的所有函数实现: setrules 到 handle_backupdb/restoredb] ...
# 请确保这里包含了之前版本的所有函数：
# handle_setrules, handle_addrule, handle_delrule, handle_listrules, handle_clearrules
# handle_listchats, handle_chatinfo, handle_cleanchats, handle_leave
# handle_preview
# handle_addkw, handle_listkw, handle_delkw
# handle_addreplace, handle_delreplace, handle_listreplace
# handle_setfooter, handle_delfooter
# handle_lock, handle_unlock
# handle_stats
# handle_addadmin, handle_deladmin, handle_listadmins
# handle_addforward, handle_delforward, handle_listforward
# handle_backupdb, handle_restoredb

async def handle_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限管理该频道（需为频道管理员）。")
            return
        rule_list = [r.strip() for r in args[2].split(",") if r.strip()]
        clear_rules(chat_id)
        for r in rule_list:
            add_rule(chat_id, r)
        await msg.reply_text(f"✅ 已为频道 {chat_id} 设置规则：{', '.join(rule_list) or '(空)'}")
    else:
        await msg.reply_text("❌ 用法错误：/setrules -100频道ID 规则1,规则2,...")


async def handle_addrule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id, rule = args[1], args[2]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限管理该频道。")
            return
        add_rule(chat_id, rule)
        await msg.reply_text(f"✅ 已为频道 {chat_id} 增加规则：{rule}")
    else:
        await msg.reply_text("❌ 用法错误：/addrule -100频道ID 规则")


async def handle_delrule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id, rule = args[1], args[2]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限管理该频道。")
            return
        delete_rule(chat_id, rule)
        await msg.reply_text(f"🗑 已为频道 {chat_id} 删除规则：{rule}")
    else:
        await msg.reply_text("❌ 用法错误：/delrule -100频道ID 规则")


async def handle_listrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限查看该频道。")
            return
        rules = get_rules(chat_id)
        if not rules:
            await msg.reply_text("📭 当前频道未设置任何规则。")
            return
        reply = f"📋 频道 {chat_id} 的规则列表：\n\n" + "\n".join(f"• {r}" for r in rules)
        await msg.reply_text(reply.strip())
    else:
        await msg.reply_text("❌ 用法错误：/listrules -100频道ID")


async def handle_clearrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限管理该频道。")
            return
        clear_rules(chat_id)
        await msg.reply_text(f"🧹 已清空频道 {chat_id} 的所有规则")
    else:
        await msg.reply_text("❌ 用法错误：/clearrules -100频道ID")


async def handle_listchats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    import sqlite3
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
    reply = "📋 可管理的频道/群组列表：\n\n"
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
        import sqlite3
        conn = sqlite3.connect(DB_FILE);
        c = conn.cursor()
        c.execute("SELECT title FROM chats WHERE chat_id=?", (chat_id,))
        r = c.fetchone();
        conn.close()
        if r: title = r[0]
        rules = get_rules(chat_id)
        footer = get_footer(chat_id)
        replacements = get_replacements(chat_id)
        details = f"• 规则：{', '.join(rules) or '(未设置)'}\n"
        details += f"• 页脚：{'已设置' if footer else '(无)'}\n"
        details += f"• 替换词：{len(replacements)} 个"
        await msg.reply_text(f"📍 频道信息：\n• ID：{chat_id}\n• 名称：{title}\n{details}")
    else:
        await msg.reply_text("❌ 用法错误：/chatinfo -100频道ID")


async def handle_cleanchats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_global_admin(msg.from_user.id):
        if msg: await msg.reply_text("🚫 此命令仅限固定配置的管理员使用。")
        return
    import sqlite3
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


async def handle_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限查看该频道规则的预览。")
            return
        cleaned = clean_caption(args[2], chat_id)
        await msg.reply_text(f"🧹 清理结果：\n\n{cleaned or '(说明已被完全移除)'}")
    else:
        await msg.reply_text("❌ 用法错误：/preview -100频道ID 说明文字")


async def handle_addkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=3)
    if len(args) >= 3:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 无权操作此频道。")
            return
        is_regex = (len(args) == 4 and args[3].lower() == "regex")
        add_keyword(chat_id, args[2], is_regex=is_regex)
        await msg.reply_text(f"✅ 已添加关键词 `{args[2]}` 到频道 {chat_id}{' (regex)' if is_regex else ''}",
                             parse_mode="Markdown")
    else:
        await msg.reply_text("❌ 用法错误：/addkw -100频道ID 关键词 [regex]")


async def handle_listkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 无权操作此频道。")
            return
        kws = get_keywords(chat_id)
        if not kws:
            await msg.reply_text("📭 当前频道没有设置任何关键词。")
            return
        reply = f"📋 频道 {chat_id} 的关键词列表：\n\n" + "\n".join(
            f"• {w}{' (regex)' if is_regex else ''}" for w, is_regex in kws)
        await msg.reply_text(reply.strip())
    else:
        await msg.reply_text("❌ 用法错误：/listkw -100频道ID")


async def handle_delkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 无权操作此频道。")
            return
        delete_keyword(chat_id, args[2])
        await msg.reply_text(f"🗑 已删除频道 {chat_id} 的关键词 `{args[2]}`", parse_mode="Markdown")
    else:
        await msg.reply_text("❌ 用法错误：/delkw -100频道ID 关键词")


async def handle_addreplace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=3)
    if len(args) == 4:
        chat_id = args[1]
        old_word = args[2]
        new_word = args[3]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限管理该频道。")
            return
        add_replacement(chat_id, old_word, new_word)
        await msg.reply_text(f"✅ 频道 {chat_id}：已添加替换 `{old_word}` → `{new_word}`", parse_mode="Markdown")
    else:
        await msg.reply_text("❌ 用法错误：/addreplace -100频道ID 旧词 新词")


async def handle_delreplace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id = args[1]
        old_word = args[2]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限管理该频道。")
            return
        delete_replacement(chat_id, old_word)
        await msg.reply_text(f"🗑 频道 {chat_id}：已删除替换 `{old_word}`", parse_mode="Markdown")
    else:
        await msg.reply_text("❌ 用法错误：/delreplace -100频道ID 旧词")


async def handle_listreplace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限查看该频道。")
            return
        replacements = get_replacements(chat_id)
        if not replacements:
            await msg.reply_text("📭 当前频道未设置替换规则。")
            return
        reply = f"📋 频道 {chat_id} 的替换规则：\n\n"
        for old, new in replacements:
            reply += f"• `{old}` → `{new}`\n"
        await msg.reply_text(reply.strip(), parse_mode="Markdown")
    else:
        await msg.reply_text("❌ 用法错误：/listreplace -100频道ID")


async def handle_setfooter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id = args[1]
        footer_text = args[2]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限管理该频道。")
            return
        set_footer(chat_id, footer_text)
        await msg.reply_text(f"✅ 已设置频道 {chat_id} 的页脚：\n\n{footer_text}")
    else:
        await msg.reply_text("❌ 用法错误：/setfooter -100频道ID 页脚内容")


async def handle_delfooter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限管理该频道。")
            return
        delete_footer(chat_id)
        await msg.reply_text(f"🗑 已删除频道 {chat_id} 的页脚")
    else:
        await msg.reply_text("❌ 用法错误：/delfooter -100频道ID")


async def handle_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 无权操作此频道。")
            return
        lock_chat(chat_id)
        await msg.reply_text(f"🔒 已锁定频道 {chat_id}，暂停清理")
    else:
        await msg.reply_text("❌ 用法错误：/lock -100频道ID")


async def handle_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 无权操作此频道。")
            return
        unlock_chat(chat_id)
        await msg.reply_text(f"🔓 已解锁频道 {chat_id}，恢复清理")
    else:
        await msg.reply_text("❌ 用法错误：/unlock -100频道ID")


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
    reply = "📊 清理统计：\n\n" + "\n".join(f"• `{cid}` → {count} 次" for cid, count in allowed_rows)
    await msg.reply_text(reply.strip(), parse_mode="Markdown")


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


async def handle_addforward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        source_id = args[1]
        target_id = args[2]
        if not await check_chat_permission(msg.from_user.id, source_id, context):
            await msg.reply_text("🚫 你没有权限管理源频道。")
            return
        add_forward(source_id, target_id)
        await msg.reply_text(f"✅ 已添加转发映射：{source_id} → {target_id}")
    else:
        await msg.reply_text("❌ 用法错误：/addforward -100源频道ID -100目标频道ID")


async def handle_delforward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        source_id = args[1]
        if not await check_chat_permission(msg.from_user.id, source_id, context):
            await msg.reply_text("🚫 你没有权限管理源频道。")
            return
        del_forward(source_id, args[2])
        await msg.reply_text(f"🗑 已移除转发映射：{source_id} → {args[2]}")
    else:
        await msg.reply_text("❌ 用法错误：/delforward -100源频道ID -100目标频道ID")


async def handle_listforward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        source_id = args[1]
        if not await check_chat_permission(msg.from_user.id, source_id, context):
            await msg.reply_text("🚫 你没有权限管理源频道。")
            return
        targets = list_forward(source_id)
        if not targets:
            await msg.reply_text(f"📭 频道 {source_id} 暂无转发目标。")
            return
        reply = "📦 转发映射列表：\n\n" + "\n".join(f"• {source_id} → {t}" for t in targets)
        await msg.reply_text(reply)
    else:
        await msg.reply_text("❌ 用法错误：/listforward -100源频道ID")


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
# [新增] 日志频道管理
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
        # 尝试发送一条测试消息
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
    set_log_channel("")  # 清空
    await msg.reply_text("✅ 已关闭日志频道功能")


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg):
        return

    role = "固定管理员" if is_global_admin(msg.from_user.id) else "动态管理员"
    extra_note = "（仅限其管理的频道）" if role == "动态管理员" else ""

    await msg.reply_text(f"""
🤖 *Jaikcl_Bot 管理命令帮助*
身份：{role}

📌 频道 ID 请使用 `-100` 开头格式。以下命令可直接点击复制使用：

*🧩 组合规则管理 {extra_note}*
`/setrules -100频道ID 规则1,规则2,...`
`/addrule -100频道ID 规则`
`/delrule -100频道ID 规则`
`/listrules -100频道ID`
`/clearrules -100频道ID`

📖 *规则示例*：
- `keep_all`：保留所有说明文字  
- `strip_all_if_links`：如含链接则整段删除  
- `clean_links`：清除链接但保留文字  
- `remove_at_prefix`：删除 @前缀  
- `block_keywords`：启用关键词屏蔽  
- `maxlen:50`：说明文字超过 50 字则删除

*🔑 关键词管理 {extra_note}*
`/addkw -100频道ID 关键词 [regex]`
`/delkw -100频道ID 关键词`
`/listkw -100频道ID`

*🔄 关键词替换 {extra_note}*
`/addreplace -100频道ID 旧词 新词`
`/delreplace -100频道ID 旧词`
`/listreplace -100频道ID`

*📝 自定义页脚 {extra_note}*
`/setfooter -100频道ID 页脚内容`
`/delfooter -100频道ID`

*🔒 清理控制 {extra_note}*
`/lock -100频道ID`
`/unlock -100频道ID`

*📊 统计与管理*
`/stats` - 查看统计
`/listchats` - 查看 Bot 所在频道列表
`/chatinfo -100频道ID` - 查看频道详情

*⚙️ 系统管理（仅固定管理员）*
`/cleanchats` - 清理无效群组数据
`/leave -100频道ID` - 强制退出群组
`/setlog -100频道ID` - 设置日志频道
`/dellog` - 关闭日志记录
`/addadmin 用户ID` - 添加动态管理员
`/deladmin 用户ID` - 移除动态管理员
`/listadmins` - 查看管理员列表
`/backupdb` - 备份数据库
`/restoredb` - 恢复数据库

*🔁 转发映射 {extra_note}*
`/addforward -100源ID -100目标ID`
`/delforward -100源ID -100目标ID`
`/listforward -100源ID`

*🧹 说明预览*
`/preview -100频道ID 说明`
""".strip(), parse_mode="Markdown")