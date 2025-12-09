# handlers/chat_mgmt.py
from telegram import Update
from telegram.ext import ContextTypes
from db import *
from cleaner import clean_caption
from handlers.utils import is_admin, check_chat_permission, reply_success, is_global_admin


async def handle_setquiet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        chat_id, mode = args[1], args[2].lower()
        if mode not in ['off', 'quiet', 'autodel']:
            await msg.reply_text("❌ 模式错误。可选：`off`, `quiet`, `autodel`", parse_mode="Markdown")
            return
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 无权");
            return
        set_quiet_mode(chat_id, mode)
        await msg.reply_text(f"✅ 频道 {chat_id} 模式：{mode}")
    else:
        await msg.reply_text("❌ 用法：/setquiet -100xxx [off/quiet/autodel]")


async def handle_setvoting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3:
        chat_id, state = args[1], args[2].lower()
        if state not in ['on', 'off']: return
        if not await check_chat_permission(msg.from_user.id, chat_id, context):
            await msg.reply_text("🚫 无权");
            return
        set_voting_enabled(chat_id, state == 'on')
        await reply_success(msg, context, f"频道 {chat_id} 投票：{state}", chat_id)
    else:
        await msg.reply_text("❌ 用法：/setvoting -100xxx [on/off]")


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


# [修改] 关键词添加：支持批量和全群
async def handle_addkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    # 按空格全部分割
    args = msg.text.strip().split()

    # 至少需要 /addkw target kw1 (3个参数)
    if len(args) < 3:
        await msg.reply_text(
            "❌ 用法：\n单群批量：`/addkw -100xxx 词1 词2... [regex]`\n全群批量：`/addkw all 词1 词2... [regex]`",
            parse_mode="Markdown")
        return

    target_input = args[1]
    keywords = args[2:]

    # 检查是否开启正则模式
    is_regex = False
    if keywords and keywords[-1].lower() == 'regex':
        is_regex = True
        keywords.pop()  # 移除最后的 'regex' 标记

    if not keywords:
        await msg.reply_text("❌ 未指定关键词。")
        return

    # 确定目标群组
    target_chats = []

    if target_input.lower() == 'all':
        # 全群操作仅限固定超级管理员
        if not is_global_admin(msg.from_user.id):
            await msg.reply_text("🚫 只有固定管理员可以使用 `all` 操作所有群组。")
            return
        target_chats = get_all_chat_ids()
    else:
        # 单群操作
        if not await check_chat_permission(msg.from_user.id, target_input, context):
            await msg.reply_text("🚫 无权管理该群组。")
            return
        target_chats = [target_input]

    if not target_chats:
        await msg.reply_text("📭 数据库中暂时没有任何群组记录。")
        return

    # 执行添加
    for cid in target_chats:
        for kw in keywords:
            add_keyword(cid, kw, is_regex)

    mode_str = " (正则)" if is_regex else ""
    target_desc = "所有已记录群组" if target_input.lower() == 'all' else target_input

    # 结果反馈
    reply_msg = f"✅ 已向 `{target_desc}` 添加 {len(keywords)} 个关键词{mode_str}：\n`{' '.join(keywords)}`"
    if target_input.lower() == 'all':
        reply_msg += f"\n(共影响 {len(target_chats)} 个群组)"

    await reply_success(msg, context, reply_msg, str(msg.chat_id))


async def handle_listkw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        kws = get_keywords(chat_id)
        await msg.reply_text(
            f"📋 关键词：\n" + "\n".join(f"• {w} {'(regex)' if r else ''}" for w, r in kws) if kws else "📭 空")


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


# [新增] 关键词自动回复
async def handle_addtrigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    # 格式: /addtrigger -100xxx 关键词 内容
    args = msg.text.strip().split(maxsplit=3)
    if len(args) == 4 and args[1].startswith("-100"):
        chat_id, kw, text = args[1], args[2].lower(), args[3]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        add_trigger(chat_id, kw, text)
        await reply_success(msg, context, f"✅ 触发器已加: {kw}", chat_id)
    else:
        await msg.reply_text("❌ 用法: `/addtrigger -100xxx 关键词 回复内容`", parse_mode="Markdown")


async def handle_deltrigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 3 and args[1].startswith("-100"):
        chat_id, kw = args[1], args[2].lower()
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        del_trigger(chat_id, kw)
        await reply_success(msg, context, f"🗑 触发器已删: {kw}", chat_id)
    else:
        await msg.reply_text("❌ 用法: `/deltrigger -100xxx 关键词`", parse_mode="Markdown")


async def handle_listtriggers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not await is_admin(msg): return
    args = msg.text.strip().split()
    if len(args) == 2:
        chat_id = args[1]
        if not await check_chat_permission(msg.from_user.id, chat_id, context): return
        triggers = get_triggers(chat_id)
        await msg.reply_text(
            f"📋 触发器:\n" + "\n".join(f"• `{k}` → {v[:20]}..." for k, v in triggers.items()) if triggers else "📭 空",
            parse_mode="Markdown")