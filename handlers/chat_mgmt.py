# handlers/chat_mgmt.py
from telegram import Update
from telegram.ext import ContextTypes
from db import *
from cleaner import clean_caption
from handlers.utils import admin_only, check_chat_permission, reply_success, is_global_admin
from locales import get_text


@admin_only
async def handle_setquiet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(get_text("quiet_usage"), parse_mode="Markdown")
        return

    chat_id, mode = context.args[0], context.args[1].lower()
    if mode not in ['off', 'quiet', 'autodel']:
        await update.message.reply_text(get_text("quiet_usage"), parse_mode="Markdown")
        return

    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await set_quiet_mode(chat_id, mode)
    await reply_success(update.message, context, get_text("quiet_set", chat_id, mode), chat_id)


@admin_only
async def handle_setvoting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(get_text("vote_usage"), parse_mode="Markdown")
        return

    chat_id, state = context.args[0], context.args[1].lower()
    if state not in ['on', 'off']:
        await update.message.reply_text(get_text("vote_usage"), parse_mode="Markdown")
        return

    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await set_voting_enabled(chat_id, state == 'on')
    await reply_success(update.message, context, get_text("vote_set", chat_id, state), chat_id)


@admin_only
async def handle_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # [升级] 支持 'all' 关键字进行批量设置
    if len(context.args) < 2:
        await update.message.reply_text("❌ 用法：`/setrules -100xxx(或all) 规则1,规则2...`", parse_mode="Markdown")
        return

    target_input = context.args[0]
    rule_str = " ".join(context.args[1:])
    rule_list = [r.strip() for r in rule_str.split(",") if r.strip()]

    target_chats = []
    if target_input.lower() == 'all':
        # 仅超级管理员可操作 'all'
        if not is_global_admin(update.message.from_user.id):
            await update.message.reply_text(get_text("no_permission"))
            return
        target_chats = await get_all_chat_ids()
    else:
        if not await check_chat_permission(update.message.from_user.id, target_input, context):
            await update.message.reply_text(get_text("no_permission"))
            return
        target_chats = [target_input]

    if not target_chats:
        await update.message.reply_text(get_text("not_found"))
        return

    # 批量应用
    for cid in target_chats:
        await clear_rules(cid)
        for r in rule_list:
            await add_rule(cid, r)

    # 回复反馈
    if target_input.lower() == 'all':
        await reply_success(update.message, context, f"✅ 已重置所有 {len(target_chats)} 个频道的规则。",
                            str(update.message.chat_id))
    else:
        await reply_success(update.message, context, get_text("success"), target_input)


@admin_only
async def handle_addrule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # [升级] 支持 'all' 关键字进行批量添加
    if len(context.args) < 2:
        await update.message.reply_text("❌ 用法：`/addrule -100xxx(或all) <规则>`", parse_mode="Markdown")
        return

    target_input = context.args[0]
    rule = " ".join(context.args[1:])

    target_chats = []
    if target_input.lower() == 'all':
        if not is_global_admin(update.message.from_user.id):
            await update.message.reply_text(get_text("no_permission"))
            return
        target_chats = await get_all_chat_ids()
    else:
        if not await check_chat_permission(update.message.from_user.id, target_input, context):
            await update.message.reply_text(get_text("no_permission"))
            return
        target_chats = [target_input]

    if not target_chats:
        await update.message.reply_text(get_text("not_found"))
        return

    for cid in target_chats:
        await add_rule(cid, rule)

    if target_input.lower() == 'all':
        await reply_success(update.message, context, f"✅ 已为所有 {len(target_chats)} 个频道添加规则：`{rule}`",
                            str(update.message.chat_id))
    else:
        await reply_success(update.message, context, get_text("rule_added"), target_input)


@admin_only
async def handle_delrule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # [升级] 支持 'all' 关键字进行批量删除
    if len(context.args) < 2:
        await update.message.reply_text("❌ 用法：`/delrule -100xxx(或all) <规则>`", parse_mode="Markdown")
        return

    target_input = context.args[0]
    rule = " ".join(context.args[1:])

    target_chats = []
    if target_input.lower() == 'all':
        if not is_global_admin(update.message.from_user.id):
            await update.message.reply_text(get_text("no_permission"))
            return
        target_chats = await get_all_chat_ids()
    else:
        if not await check_chat_permission(update.message.from_user.id, target_input, context):
            await update.message.reply_text(get_text("no_permission"))
            return
        target_chats = [target_input]

    if not target_chats:
        await update.message.reply_text(get_text("not_found"))
        return

    for cid in target_chats:
        await delete_rule(cid, rule)

    if target_input.lower() == 'all':
        await reply_success(update.message, context, f"🗑 已从所有 {len(target_chats)} 个频道移除规则：`{rule}`",
                            str(update.message.chat_id))
    else:
        await reply_success(update.message, context, get_text("rule_deleted"), target_input)


@admin_only
async def handle_listrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ 用法：`/listrules -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    rules = await get_rules(chat_id)
    await update.message.reply_text(f"📋 规则：\n" + "\n".join(f"• {r}" for r in rules) if rules else get_text("no_data"))


@admin_only
async def handle_clearrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # [升级] 支持 'all' 关键字进行批量清空
    if len(context.args) < 1:
        await update.message.reply_text("❌ 用法：`/clearrules -100xxx(或all)`", parse_mode="Markdown")
        return

    target_input = context.args[0]

    target_chats = []
    if target_input.lower() == 'all':
        if not is_global_admin(update.message.from_user.id):
            await update.message.reply_text(get_text("no_permission"))
            return
        target_chats = await get_all_chat_ids()
    else:
        if not await check_chat_permission(update.message.from_user.id, target_input, context):
            await update.message.reply_text(get_text("no_permission"))
            return
        target_chats = [target_input]

    if not target_chats:
        await update.message.reply_text(get_text("not_found"))
        return

    for cid in target_chats:
        await clear_rules(cid)

    msg_text = get_text("rules_cleared",
                        target_input) if target_input.lower() != 'all' else f"🧹 已清空所有 {len(target_chats)} 个频道的规则。"
    await reply_success(update.message, context, msg_text, str(update.message.chat_id))


@admin_only
async def handle_addkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(get_text("args_error") + "\n示例: `/addkw -100xxx 关键词`",
                                        parse_mode="Markdown")
        return

    target_input = context.args[0]
    keywords = context.args[1:]

    is_regex = False
    if keywords and keywords[-1].lower() == 'regex':
        is_regex = True
        keywords.pop()

    if not keywords: return

    target_chats = []
    if target_input.lower() == 'all':
        if not is_global_admin(update.message.from_user.id):
            await update.message.reply_text(get_text("no_permission"))
            return
        target_chats = await get_all_chat_ids()
    else:
        if not await check_chat_permission(update.message.from_user.id, target_input, context):
            await update.message.reply_text(get_text("no_permission"))
            return
        target_chats = [target_input]

    if not target_chats:
        await update.message.reply_text(get_text("not_found"))
        return

    for cid in target_chats:
        for kw in keywords:
            await add_keyword(cid, kw, is_regex)

    target_desc = "ALL" if target_input.lower() == 'all' else target_input
    await reply_success(update.message, context, get_text("kw_added", target_desc, len(keywords)),
                        str(update.message.chat_id))


@admin_only
async def handle_listkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ 用法：`/listkw -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    kws = await get_keywords(chat_id)
    await update.message.reply_text(
        f"📋 关键词：\n" + "\n".join(f"• {w} {'(regex)' if r else ''}" for w, r in kws) if kws else get_text("no_data"))


@admin_only
async def handle_delkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ 用法：`/delkw -100xxx <关键词>`", parse_mode="Markdown")
        return
    chat_id, kw = context.args[0], context.args[1]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await delete_keyword(chat_id, kw)
    await reply_success(update.message, context, get_text("kw_deleted"), chat_id)


@admin_only
async def handle_addreplace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("❌ 用法：`/addreplace -100xxx <旧词> <新词>`", parse_mode="Markdown")
        return
    chat_id, old, new = context.args[0], context.args[1], context.args[2]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await add_replacement(chat_id, old, new)
    await reply_success(update.message, context, get_text("success"), chat_id)


@admin_only
async def handle_delreplace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ 用法：`/delreplace -100xxx <旧词>`", parse_mode="Markdown")
        return
    chat_id, old = context.args[0], context.args[1]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await delete_replacement(chat_id, old)
    await reply_success(update.message, context, get_text("deleted"), chat_id)


@admin_only
async def handle_listreplace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ 用法：`/listreplace -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    reps = await get_replacements(chat_id)
    await update.message.reply_text(
        f"📋 替换：\n" + "\n".join(f"• {o} -> {n}" for o, n in reps) if reps else get_text("no_data"))


@admin_only
async def handle_setfooter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ 用法：`/setfooter -100xxx <内容>`", parse_mode="Markdown")
        return
    chat_id, text = context.args[0], " ".join(context.args[1:])
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await set_footer(chat_id, text)
    await reply_success(update.message, context, get_text("footer_set"), chat_id)


@admin_only
async def handle_delfooter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ 用法：`/delfooter -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await delete_footer(chat_id)
    await reply_success(update.message, context, get_text("footer_deleted"), chat_id)


@admin_only
async def handle_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ 用法：`/lock -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await lock_chat(chat_id)
    await reply_success(update.message, context, get_text("locked"), chat_id)


@admin_only
async def handle_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ 用法：`/unlock -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await unlock_chat(chat_id)
    await reply_success(update.message, context, get_text("unlocked"), chat_id)


@admin_only
async def handle_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ 用法：`/preview -100xxx <测试文本>`", parse_mode="Markdown")
        return
    chat_id, text = context.args[0], " ".join(context.args[1:])
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    cleaned = await clean_caption(text, chat_id, update.message.from_user.id, update.message.entities)
    await update.message.reply_text(f"🧹 结果：\n\n{cleaned or '(已删除)'}")


@admin_only
async def handle_addforward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ 用法：`/addforward -100源ID -100目标ID`", parse_mode="Markdown")
        return
    source, target = context.args[0], context.args[1]
    if not await check_chat_permission(update.message.from_user.id, source, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await add_forward(source, target)
    await reply_success(update.message, context, get_text("forward_added", source, target), source)


@admin_only
async def handle_delforward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ 用法：`/delforward -100源ID -100目标ID`", parse_mode="Markdown")
        return
    source, target = context.args[0], context.args[1]
    if not await check_chat_permission(update.message.from_user.id, source, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await del_forward(source, target)
    await reply_success(update.message, context, get_text("forward_deleted"), source)


@admin_only
async def handle_listforward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ 用法：`/listforward -100xxx`", parse_mode="Markdown")
        return
    source = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, source, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    tgts = await list_forward(source)
    await update.message.reply_text(
        f"📋 转发目标：\n" + "\n".join(f"• {t}" for t in tgts) if tgts else get_text("no_data"))


@admin_only
async def handle_allowuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ 用法：`/allowuser -100xxx <用户ID>`", parse_mode="Markdown")
        return
    chat_id, uid = context.args[0], context.args[1]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await add_user_whitelist(chat_id, uid)
    await reply_success(update.message, context, get_text("whitelist_added", uid), chat_id)


@admin_only
async def handle_blockuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ 用法：`/blockuser -100xxx <用户ID>`", parse_mode="Markdown")
        return
    chat_id, uid = context.args[0], context.args[1]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await del_user_whitelist(chat_id, uid)
    await reply_success(update.message, context, get_text("whitelist_deleted", uid), chat_id)


@admin_only
async def handle_listallowed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ 用法：`/listallowed -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    users = await get_chat_whitelist(chat_id)
    await update.message.reply_text(
        f"📋 白名单：\n" + "\n".join(f"• {u}" for u in users) if users else get_text("no_data"))


@admin_only
async def handle_addtrigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("❌ 用法: `/addtrigger -100xxx 关键词 回复内容`", parse_mode="Markdown")
        return
    chat_id, kw, text = context.args[0], context.args[1].lower(), " ".join(context.args[2:])
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await add_trigger(chat_id, kw, text)
    await reply_success(update.message, context, get_text("trigger_added", kw), chat_id)


@admin_only
async def handle_deltrigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ 用法: `/deltrigger -100xxx 关键词`", parse_mode="Markdown")
        return
    chat_id, kw = context.args[0], context.args[1].lower()
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    await del_trigger(chat_id, kw)
    await reply_success(update.message, context, get_text("trigger_deleted", kw), chat_id)


@admin_only
async def handle_listtriggers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ 用法: `/listtriggers -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    triggers = await get_triggers(chat_id)
    await update.message.reply_text(
        f"📋 触发器:\n" + "\n".join(f"• `{k}` → {v[:20]}..." for k, v in triggers.items()) if triggers else get_text(
            "no_data"),
        parse_mode="Markdown")