# handlers/chat_mgmt.py
from telegram import Update
from telegram.ext import ContextTypes
from db import *
from cleaner import clean_caption
from handlers.utils import is_admin, check_chat_permission, reply_success

async def handle_setquiet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        chat_id, mode = args[1], args[2].lower()
        if mode not in ['off', 'quiet', 'autodel']: return
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 无权"); return
        set_quiet_mode(chat_id, mode)
        await msg.reply_text(f"✅ 频道 {chat_id} 模式：{mode}")
    else: await msg.reply_text("❌ 用法：/setquiet -100xxx [off/quiet/autodel]")

async def handle_setvoting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        chat_id, state = args[1], args[2].lower()
        if state not in ['on', 'off']: return
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 无权"); return
        set_voting_enabled(chat_id, state == 'on')
        await reply_success(msg, context, f"频道 {chat_id} 投票：{state}", chat_id)
    else: await msg.reply_text("❌ 用法：/setvoting -100xxx [on/off]")

async def handle_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        rule_list = [r.strip() for r in args[2].split(",") if r.strip()]
        clear_rules(chat_id)
        for r in rule_list: add_rule(chat_id, r)
        await reply_success(msg, context, f"✅ 规则已设", chat_id)

async def handle_addrule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id, rule = args[1], args[2]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        add_rule(chat_id, rule)
        await reply_success(msg, context, f"✅ 规则已加", chat_id)

async def handle_delrule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id, rule = args[1], args[2]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        delete_rule(chat_id, rule)
        await reply_success(msg, context, f"🗑 规则已删", chat_id)

async def handle_listrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        rules = get_rules(chat_id)
        await msg.reply_text(f"📋 规则：\n" + "\n".join(f"• {r}" for r in rules) if rules else "📭 空")

async def handle_clearrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        clear_rules(chat_id)
        await reply_success(msg, context, f"🧹 规则已清空", chat_id)

async def handle_addkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=3)
    if len(args) >= 3:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        regex = (len(args) == 4 and args[3].lower() == "regex")
        add_keyword(chat_id, args[2], regex)
        await reply_success(msg, context, f"✅ 关键词已加", chat_id)

async def handle_listkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        kws = get_keywords(chat_id)
        await msg.reply_text(f"📋 关键词：\n" + "\n".join(f"• {w} {'(regex)' if r else ''}" for w, r in kws) if kws else "📭 空")

async def handle_delkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        delete_keyword(chat_id, args[2])
        await reply_success(msg, context, f"🗑 关键词已删", chat_id)

async def handle_addreplace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=3)
    if len(args) == 4:
        chat_id, old, new = args[1], args[2], args[3]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        add_replacement(chat_id, old, new)
        await reply_success(msg, context, f"✅ 替换已加", chat_id)

async def handle_delreplace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id, old = args[1], args[2]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        delete_replacement(chat_id, old)
        await reply_success(msg, context, f"🗑 替换已删", chat_id)

async def handle_listreplace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        reps = get_replacements(chat_id)
        await msg.reply_text(f"📋 替换：\n" + "\n".join(f"• {o} -> {n}" for o, n in reps) if reps else "📭 空")

async def handle_setfooter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id, text = args[1], args[2]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        set_footer(chat_id, text)
        await reply_success(msg, context, f"✅ 页脚已设", chat_id)

async def handle_delfooter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        delete_footer(chat_id)
        await reply_success(msg, context, f"🗑 页脚已删", chat_id)

async def handle_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        lock_chat(chat_id)
        await reply_success(msg, context, "🔒 已锁定", chat_id)

async def handle_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        unlock_chat(chat_id)
        await reply_success(msg, context, "🔓 已解锁", chat_id)

async def handle_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split(maxsplit=2)
    if len(args) == 3:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        cleaned = clean_caption(args[2], chat_id, msg.from_user.id, msg.entities)
        await msg.reply_text(f"🧹 结果：\n\n{cleaned or '(已删除)'}")

async def handle_addforward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        source, target = args[1], args[2]
        if not await check_chat_permission(msg.from_user.id, source, context): return
        add_forward(source, target)
        await reply_success(msg, context, f"✅ 转发已加", source)

async def handle_delforward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        source, target = args[1], args[2]
        if not await check_chat_permission(msg.from_user.id, source, context): return
        del_forward(source, target)
        await reply_success(msg, context, f"🗑 转发已删", source)

async def handle_listforward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        source = args[1]
        if not await check_chat_permission(msg.from_user.id, source, context): return
        tgts = list_forward(source)
        await msg.reply_text(f"📋 转发目标：\n" + "\n".join(f"• {t}" for t in tgts) if tgts else "📭 空")

async def handle_allowuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        chat_id, uid = args[1], args[2]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        add_user_whitelist(chat_id, uid)
        await reply_success(msg, context, f"✅ 白名单已加 {uid}", chat_id)

async def handle_blockuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        chat_id, uid = args[1], args[2]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        del_user_whitelist(chat_id, uid)
        await reply_success(msg, context, f"🗑 白名单已删 {uid}", chat_id)

async def handle_listallowed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        users = get_chat_whitelist(chat_id)
        await msg.reply_text(f"📋 白名单：\n" + "\n".join(f"• {u}" for u in users) if users else "📭 空")