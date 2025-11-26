# handlers/chat_mgmt.py
# 群组管理命令：规则、关键词、页脚、白名单、转发、静音等

from telegram import Update
from telegram.ext import ContextTypes
from db import *
from cleaner import clean_caption
from handlers.utils import is_admin, check_chat_permission, reply_success


# =========================
# 静音/清理模式
# =========================
async def handle_setquiet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()

    # 用法：/setquiet -100xxx [off/quiet/autodel]
    if len(args) == 3:
        chat_id = args[1]
        mode = args[2].lower()

        if mode not in ['off', 'quiet', 'autodel']:
            await msg.reply_text("❌ 模式错误。可选：`off` (默认), `quiet` (静音), `autodel` (阅后即焚)",
                                 parse_mode="Markdown")
            return

        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限管理该频道。")
            return

        set_quiet_mode(chat_id, mode)

        desc = {
            "off": "🔔 正常模式（默认）",
            "quiet": "🔕 静音模式（不提示成功信息）",
            "autodel": "🔥 阅后即焚（提示后10秒自动删除）"
        }
        # 设置命令本身总是回复，不受静音影响，否则管理员不知道设好了没
        await msg.reply_text(f"✅ 频道 {chat_id} 已设置为：{desc[mode]}")
    else:
        await msg.reply_text("❌ 用法错误：`/setquiet -100频道ID [off/quiet/autodel]`", parse_mode="Markdown")


# =========================
# 规则管理
# =========================
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

        # [修改] 使用 reply_success
        await reply_success(msg, context, f"✅ 已为频道 {chat_id} 设置规则：{', '.join(rule_list) or '(空)'}", chat_id)
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
        await reply_success(msg, context, f"✅ 已为频道 {chat_id} 增加规则：{rule}", chat_id)
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
        await reply_success(msg, context, f"🗑 已为频道 {chat_id} 删除规则：{rule}", chat_id)
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
        await reply_success(msg, context, f"🧹 已清空频道 {chat_id} 的所有规则", chat_id)
    else:
        await msg.reply_text("❌ 用法错误：/clearrules -100频道ID")


# =========================
# 关键词管理
# =========================
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
        await reply_success(msg, context,
                            f"✅ 已添加关键词 `{args[2]}` 到频道 {chat_id}{' (regex)' if is_regex else ''}", chat_id)
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
        await reply_success(msg, context, f"🗑 已删除频道 {chat_id} 的关键词 `{args[2]}`", chat_id)
    else:
        await msg.reply_text("❌ 用法错误：/delkw -100频道ID 关键词")


# =========================
# 关键词替换
# =========================
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
        await reply_success(msg, context, f"✅ 频道 {chat_id}：已添加替换 `{old_word}` → `{new_word}`", chat_id)
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
        await reply_success(msg, context, f"🗑 频道 {chat_id}：已删除替换 `{old_word}`", chat_id)
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


# =========================
# 页脚管理
# =========================
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
        await reply_success(msg, context, f"✅ 已设置频道 {chat_id} 的页脚：\n\n{footer_text}", chat_id)
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
        await reply_success(msg, context, f"🗑 已删除频道 {chat_id} 的页脚", chat_id)
    else:
        await msg.reply_text("❌ 用法错误：/delfooter -100频道ID")


# =========================
# 锁定/解锁
# =========================
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
        await reply_success(msg, context, f"🔒 已锁定频道 {chat_id}，暂停清理", chat_id)
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
        await reply_success(msg, context, f"🔓 已解锁频道 {chat_id}，恢复清理", chat_id)
    else:
        await msg.reply_text("❌ 用法错误：/unlock -100频道ID")


# =========================
# 预览
# =========================
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


# =========================
# 转发映射
# =========================
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
        await reply_success(msg, context, f"✅ 已添加转发映射：{source_id} → {target_id}", source_id)
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
        await reply_success(msg, context, f"🗑 已移除转发映射：{source_id} → {args[2]}", source_id)
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


# =========================
# 用户白名单管理
# =========================
async def handle_allowuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        chat_id = args[1]
        user_id = args[2]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限管理该频道。")
            return
        add_user_whitelist(chat_id, user_id)
        await reply_success(msg, context, f"✅ 已将用户 `{user_id}` 加入频道 {chat_id} 的白名单。", chat_id)
    else:
        await msg.reply_text("❌ 用法错误：/allowuser -100频道ID 用户ID")


async def handle_blockuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        chat_id = args[1]
        user_id = args[2]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限管理该频道。")
            return
        del_user_whitelist(chat_id, user_id)
        await reply_success(msg, context, f"🗑 已将用户 `{user_id}` 从频道 {chat_id} 的白名单中移除。", chat_id)
    else:
        await msg.reply_text("❌ 用法错误：/blockuser -100频道ID 用户ID")


async def handle_listallowed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 你没有权限查看该频道。")
            return
        users = get_chat_whitelist(chat_id)
        if not users:
            await msg.reply_text(f"📭 频道 {chat_id} 暂无白名单用户。")
            return
        reply = f"📋 频道 {chat_id} 的白名单用户：\n\n" + "\n".join(f"• `{uid}`" for uid in users)
        await msg.reply_text(reply.strip(), parse_mode="Markdown")
    else:
        await msg.reply_text("❌ 用法错误：/listallowed -100频道ID")