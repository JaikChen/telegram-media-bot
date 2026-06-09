# handlers/chat_mgmt.py
"""
Chat management handlers for configuring bot behavior in specific chats.
Includes quiet mode, voting, rules, keywords, replacements, footers, and locks.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.data.repositories import ChatRepository, VoteRepository
from src.cleaner.engine import clean_caption
from src.bot.core.locales import get_text
from src.bot.utils.helpers import admin_only, check_chat_permission, reply_success, is_global_admin, log_event

logger = logging.getLogger(__name__)


@admin_only
async def handle_setquiet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set quiet mode for a chat (off/quiet/autodel)."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text(get_text("quiet_usage"), parse_mode="Markdown")
        return

    chat_id, mode = context.args[0], context.args[1].lower()
    if mode not in ["off", "quiet", "autodel"]:
        await update.message.reply_text(get_text("quiet_usage"), parse_mode="Markdown")
        return

    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.set_quiet_mode(chat_id, mode)
        await reply_success(update.message, context, get_text("quiet_set", chat_id, mode), chat_id)
        logger.info(f"⚙️ [设置] 静默模式设定为 {mode} -> {chat_id}")
        await log_event(
            context.bot,
            f"⚙️ <b>静默模式变更</b>\n频道: <code>{chat_id}</code>\n模式: <code>{mode}</code>",
            category="config",
        )
    except Exception as e:
        logger.error(f"Error in handle_setquiet: {e}")
        await update.message.reply_text(get_text("error_occurred"))


@admin_only
async def handle_setvoting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable or disable voting buttons for a chat."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text(get_text("vote_usage"), parse_mode="Markdown")
        return

    chat_id, state = context.args[0], context.args[1].lower()
    if state not in ["on", "off"]:
        await update.message.reply_text(get_text("vote_usage"), parse_mode="Markdown")
        return

    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        enabled = state == "on"
        await VoteRepository.set_voting_enabled(chat_id, enabled)
        await reply_success(update.message, context, get_text("vote_set", chat_id, state), chat_id)
        logger.info(f"Voting {'enabled' if enabled else 'disabled'} for chat {chat_id} by {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in handle_setvoting: {e}")


@admin_only
async def handle_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset and set rules for a chat or 'all' chats."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text("❌ 用法：`/setrules -100xxx(或all) 规则1,规则2...`", parse_mode="Markdown")
        return

    target_input = context.args[0]
    rule_str = " ".join(context.args[1:])
    rule_list = [r.strip() for r in rule_str.split(",") if r.strip()]

    try:
        target_chats = []
        if target_input.lower() == "all":
            if not is_global_admin(update.message.from_user.id):
                await update.message.reply_text(get_text("no_permission"))
                return
            target_chats = await ChatRepository.get_all_chat_ids()
        else:
            if not await check_chat_permission(update.message.from_user.id, target_input, context):
                await update.message.reply_text(get_text("no_permission"))
                return
            target_chats = [target_input]

        if not target_chats:
            await update.message.reply_text(get_text("not_found"))
            return

        for cid in target_chats:
            await ChatRepository.clear_rules(cid)
            for r in rule_list:
                await ChatRepository.add_rule(cid, r)

        if target_input.lower() == "all":
            await reply_success(
                update.message,
                context,
                f"✅ 已重置所有 {len(target_chats)} 个频道的规则。",
                str(update.message.chat_id),
            )
        else:
            await reply_success(update.message, context, get_text("success"), target_input)
        logger.info(f"Rules reset for {target_input} by {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in handle_setrules: {e}")


@admin_only
async def handle_addrule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a rule to a chat or 'all' chats."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text("❌ 用法：`/addrule -100xxx(或all) <规则>`", parse_mode="Markdown")
        return

    target_input = context.args[0]
    rule = " ".join(context.args[1:])

    try:
        target_chats = []
        if target_input.lower() == "all":
            if not is_global_admin(update.message.from_user.id):
                await update.message.reply_text(get_text("no_permission"))
                return
            target_chats = await ChatRepository.get_all_chat_ids()
        else:
            if not await check_chat_permission(update.message.from_user.id, target_input, context):
                await update.message.reply_text(get_text("no_permission"))
                return
            target_chats = [target_input]

        if not target_chats:
            await update.message.reply_text(get_text("not_found"))
            return

        for cid in target_chats:
            await ChatRepository.add_rule(cid, rule)

        if target_input.lower() == "all":
            await reply_success(
                update.message,
                context,
                f"✅ 已为所有 {len(target_chats)} 个频道添加规则：`{rule}`",
                str(update.message.chat_id),
            )
        else:
            await reply_success(update.message, context, get_text("rule_added"), target_input)
    except Exception as e:
        logger.error(f"Error in handle_addrule: {e}")


@admin_only
async def handle_delrule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a rule from a chat or 'all' chats."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text("❌ 用法：`/delrule -100xxx(或all) <规则>`", parse_mode="Markdown")
        return

    target_input = context.args[0]
    rule = " ".join(context.args[1:])

    try:
        target_chats = []
        if target_input.lower() == "all":
            if not is_global_admin(update.message.from_user.id):
                await update.message.reply_text(get_text("no_permission"))
                return
            target_chats = await ChatRepository.get_all_chat_ids()
        else:
            if not await check_chat_permission(update.message.from_user.id, target_input, context):
                await update.message.reply_text(get_text("no_permission"))
                return
            target_chats = [target_input]

        if not target_chats:
            await update.message.reply_text(get_text("not_found"))
            return

        for cid in target_chats:
            await ChatRepository.delete_rule(cid, rule)

        if target_input.lower() == "all":
            await reply_success(
                update.message,
                context,
                f"🗑 已从所有 {len(target_chats)} 个频道移除规则：`{rule}`",
                str(update.message.chat_id),
            )
        else:
            await reply_success(update.message, context, get_text("rule_deleted"), target_input)
    except Exception as e:
        logger.error(f"Error in handle_delrule: {e}")


@admin_only
async def handle_listrules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all rules for a specific chat."""
    if not update.message or len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法：`/listrules -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        rules = await ChatRepository.get_chat_rules(chat_id)
        await update.message.reply_text(
            "📋 规则：\n" + "\n".join(f"• {r}" for r in rules) if rules else get_text("no_data")
        )
    except Exception as e:
        logger.error(f"Error in handle_listrules: {e}")


@admin_only
async def handle_clearrules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all rules for a chat or 'all' chats."""
    if not update.message or len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法：`/clearrules -100xxx(或all)`", parse_mode="Markdown")
        return

    target_input = context.args[0]

    try:
        target_chats = []
        if target_input.lower() == "all":
            if not is_global_admin(update.message.from_user.id):
                await update.message.reply_text(get_text("no_permission"))
                return
            target_chats = await ChatRepository.get_all_chat_ids()
        else:
            if not await check_chat_permission(update.message.from_user.id, target_input, context):
                await update.message.reply_text(get_text("no_permission"))
                return
            target_chats = [target_input]

        if not target_chats:
            await update.message.reply_text(get_text("not_found"))
            return

        for cid in target_chats:
            await ChatRepository.clear_rules(cid)

        msg_text = (
            get_text("rules_cleared", target_input)
            if target_input.lower() != "all"
            else f"🧹 已清空所有 {len(target_chats)} 个频道的规则。"
        )
        await reply_success(update.message, context, msg_text, str(update.message.chat_id))
    except Exception as e:
        logger.error(f"Error in handle_clearrules: {e}")


@admin_only
async def handle_addkw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add keywords to block in a chat or 'all' chats."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text(
            get_text("args_error") + "\n示例: `/addkw -100xxx 关键词`", parse_mode="Markdown"
        )
        return

    target_input = context.args[0]
    keywords = list(context.args[1:])

    is_regex = False
    if keywords and keywords[-1].lower() == "regex":
        is_regex = True
        keywords.pop()

    if not keywords:
        return

    try:
        target_chats = []
        if target_input.lower() == "all":
            if not is_global_admin(update.message.from_user.id):
                await update.message.reply_text(get_text("no_permission"))
                return
            target_chats = await ChatRepository.get_all_chat_ids()
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
                await ChatRepository.add_keyword(cid, kw, is_regex)

        target_desc = "ALL" if target_input.lower() == "all" else target_input
        await reply_success(
            update.message, context, get_text("kw_added", target_desc, len(keywords)), str(update.message.chat_id)
        )
    except Exception as e:
        logger.error(f"Error in handle_addkw: {e}")


@admin_only
async def handle_listkw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all blocked keywords for a chat."""
    if not update.message or len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法：`/listkw -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        kws = await ChatRepository.get_keywords(chat_id)
        await update.message.reply_text(
            "📋 关键词：\n" + "\n".join(f"• {w} {'(regex)' if r else ''}" for w, r in kws)
            if kws
            else get_text("no_data")
        )
    except Exception as e:
        logger.error(f"Error in handle_listkw: {e}")


@admin_only
async def handle_delkw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a blocked keyword from a chat."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text("❌ 用法：`/delkw -100xxx <关键词>`", parse_mode="Markdown")
        return
    chat_id, kw = context.args[0], context.args[1]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.delete_keyword(chat_id, kw)
        await reply_success(update.message, context, get_text("kw_deleted"), chat_id)
    except Exception as e:
        logger.error(f"Error in handle_delkw: {e}")


@admin_only
async def handle_addreplace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a text replacement rule for a chat."""
    if not update.message or len(context.args or []) < 3:
        await update.message.reply_text("❌ 用法：`/addreplace -100xxx <旧词> <新词>`", parse_mode="Markdown")
        return
    chat_id, old, new = context.args[0], context.args[1], context.args[2]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.add_replacement(chat_id, old, new)
        await reply_success(update.message, context, get_text("success"), chat_id)
    except Exception as e:
        logger.error(f"Error in handle_addreplace: {e}")


@admin_only
async def handle_delreplace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a text replacement rule from a chat."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text("❌ 用法：`/delreplace -100xxx <旧词>`", parse_mode="Markdown")
        return
    chat_id, old = context.args[0], context.args[1]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.delete_replacement(chat_id, old)
        await reply_success(update.message, context, get_text("deleted"), chat_id)
    except Exception as e:
        logger.error(f"Error in handle_delreplace: {e}")


@admin_only
async def handle_listreplace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all text replacement rules for a chat."""
    if not update.message or len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法：`/listreplace -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        reps = await ChatRepository.get_replacements(chat_id)
        await update.message.reply_text(
            "📋 替换：\n" + "\n".join(f"• {o} -> {n}" for o, n in reps) if reps else get_text("no_data")
        )
    except Exception as e:
        logger.error(f"Error in handle_listreplace: {e}")


@admin_only
async def handle_setfooter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set a footer for messages forwarded to a chat."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text("❌ 用法：`/setfooter -100xxx <内容>`", parse_mode="Markdown")
        return
    chat_id, text = context.args[0], " ".join(context.args[1:])
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.set_footer(chat_id, text)
        await reply_success(update.message, context, get_text("footer_set"), chat_id)
    except Exception as e:
        logger.error(f"Error in handle_setfooter: {e}")


@admin_only
async def handle_delfooter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete the footer for a chat."""
    if not update.message or len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法：`/delfooter -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.delete_footer(chat_id)
        await reply_success(update.message, context, get_text("footer_deleted"), chat_id)
    except Exception as e:
        logger.error(f"Error in handle_delfooter: {e}")


@admin_only
async def handle_lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lock a chat, preventing the bot from processing messages in it."""
    if not update.message or len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法：`/lock -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.lock_chat(chat_id)
        await reply_success(update.message, context, get_text("locked"), chat_id)
    except Exception as e:
        logger.error(f"Error in handle_lock: {e}")


@admin_only
async def handle_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unlock a chat, allowing the bot to process messages in it."""
    if not update.message or len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法：`/unlock -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.unlock_chat(chat_id)
        await reply_success(update.message, context, get_text("unlocked"), chat_id)
    except Exception as e:
        logger.error(f"Error in handle_unlock: {e}")


@admin_only
async def handle_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Preview how the bot would clean a specific text for a chat."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text("❌ 用法：`/preview -100xxx <测试文本>`", parse_mode="Markdown")
        return
    chat_id, text = context.args[0], " ".join(context.args[1:])
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        cleaned = await clean_caption(text, chat_id, update.message.from_user.id, update.message.entities)
        await update.message.reply_text(f"🧹 结果：\n\n{cleaned or '(已删除)'}")
    except Exception as e:
        logger.error(f"Error in handle_preview: {e}")


@admin_only
async def handle_addforward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a forwarding rule from a source chat to a target chat."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text("❌ 用法：`/addforward -100源ID -100目标ID`", parse_mode="Markdown")
        return
    source, target = context.args[0], context.args[1]
    if not await check_chat_permission(update.message.from_user.id, source, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.add_forward(source, target)
        await reply_success(update.message, context, get_text("forward_added", source, target), source)
    except Exception as e:
        logger.error(f"Error in handle_addforward: {e}")


@admin_only
async def handle_delforward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a forwarding rule."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text("❌ 用法：`/delforward -100源ID -100目标ID`", parse_mode="Markdown")
        return
    source, target = context.args[0], context.args[1]
    if not await check_chat_permission(update.message.from_user.id, source, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.del_forward(source, target)
        await reply_success(update.message, context, get_text("forward_deleted"), source)
    except Exception as e:
        logger.error(f"Error in handle_delforward: {e}")


@admin_only
async def handle_listforward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all target chats for a source chat's forwarding rules."""
    if not update.message or len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法：`/listforward -100xxx`", parse_mode="Markdown")
        return
    source = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, source, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        tgts = await ChatRepository.list_forward(source)
        await update.message.reply_text(
            "📋 转发目标：\n" + "\n".join(f"• {t}" for t in tgts) if tgts else get_text("no_data")
        )
    except Exception as e:
        logger.error(f"Error in handle_listforward: {e}")


@admin_only
async def handle_listallforwards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all active forwarding chains across the entire bot."""
    if not update.message:
        return
    if not is_global_admin(update.message.from_user.id):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        rows = await ChatRepository.list_all_forwards()
        if not rows:
            await update.message.reply_text(get_text("no_data"))
            return

        text = "📋 **全量转发链列表**：\n\n"
        # Group by source
        chains = {}
        for src, tgt in rows:
            if src not in chains:
                chains[src] = []
            chains[src].append(tgt)

        for src, tgts in chains.items():
            text += f"📍 `源: {src}`\n"
            for t in tgts:
                text += f" └─> `{t}`\n"
            text += "\n"

        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in handle_listallforwards: {e}")


@admin_only
async def handle_allowuser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a user to the whitelist for a chat, exempting them from cleaning."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text("❌ 用法：`/allowuser -100xxx <用户ID>`", parse_mode="Markdown")
        return
    chat_id, uid = context.args[0], context.args[1]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.add_user_whitelist(chat_id, uid)
        await reply_success(update.message, context, get_text("whitelist_added", uid), chat_id)
    except Exception as e:
        logger.error(f"Error in handle_allowuser: {e}")


@admin_only
async def handle_blockuser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a user from the whitelist for a chat."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text("❌ 用法：`/blockuser -100xxx <用户ID>`", parse_mode="Markdown")
        return
    chat_id, uid = context.args[0], context.args[1]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.del_user_whitelist(chat_id, uid)
        await reply_success(update.message, context, get_text("whitelist_deleted", uid), chat_id)
    except Exception as e:
        logger.error(f"Error in handle_blockuser: {e}")


@admin_only
async def handle_listallowed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all whitelisted users for a chat."""
    if not update.message or len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法：`/listallowed -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        users = await ChatRepository.get_chat_whitelist(chat_id)
        await update.message.reply_text(
            "📋 白名单：\n" + "\n".join(f"• {u}" for u in users) if users else get_text("no_data")
        )
    except Exception as e:
        logger.error(f"Error in handle_listallowed: {e}")


@admin_only
async def handle_addtrigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add an automatic reply trigger for a chat."""
    if not update.message or len(context.args or []) < 3:
        await update.message.reply_text("❌ 用法: `/addtrigger -100xxx 关键词 回复内容`", parse_mode="Markdown")
        return
    chat_id, kw, text = context.args[0], context.args[1].lower(), " ".join(context.args[2:])
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.add_trigger(chat_id, kw, text)
        await reply_success(update.message, context, get_text("trigger_added", kw), chat_id)
    except Exception as e:
        logger.error(f"Error in handle_addtrigger: {e}")


@admin_only
async def handle_deltrigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete an automatic reply trigger."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text("❌ 用法: `/deltrigger -100xxx 关键词`", parse_mode="Markdown")
        return
    chat_id, kw = context.args[0], context.args[1].lower()
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        await ChatRepository.del_trigger(chat_id, kw)
        await reply_success(update.message, context, get_text("trigger_deleted", kw), chat_id)
    except Exception as e:
        logger.error(f"Error in handle_deltrigger: {e}")


@admin_only
async def handle_listtriggers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all automatic reply triggers for a chat."""
    if not update.message or len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法: `/listtriggers -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return

    try:
        triggers = await ChatRepository.get_triggers(chat_id)
        await update.message.reply_text(
            "📋 触发器:\n" + "\n".join(f"• `{k}` → {v[:20]}..." for k, v in triggers)
            if triggers
            else get_text("no_data"),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error in handle_listtriggers: {e}")


@admin_only
async def handle_settemplate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set a caption template for a chat."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text(
            "❌ 用法: `/settemplate -100xxx <模板内容>`\n变量: `{orig}`, `{title}`, `{cid}`, `{date}`, `{user}`",
            parse_mode="Markdown",
        )
        return
    chat_id, template = context.args[0], " ".join(context.args[1:])
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return
    try:
        await ChatRepository.set_caption_template(chat_id, template)
        await reply_success(update.message, context, "✅ 模板已设置。", chat_id)
        logger.info(f"⚙️ [设置] 内容模板已更新 -> {chat_id}")
        await log_event(
            context.bot,
            f"⚙️ <b>内容模板变更</b>\n频道: <code>{chat_id}</code>\n模板: <code>{template}</code>",
            category="config",
        )
    except Exception as e:
        logger.error(f"Error in handle_settemplate: {e}")


@admin_only
async def handle_deltemplate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete the caption template for a chat."""
    if not update.message or len(context.args or []) < 1:
        await update.message.reply_text("❌ 用法: `/deltemplate -100xxx`", parse_mode="Markdown")
        return
    chat_id = context.args[0]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return
    try:
        await ChatRepository.delete_caption_template(chat_id)
        await reply_success(update.message, context, "🗑 模板已移除。", chat_id)
        logger.info(f"⚙️ [设置] 内容模板已移除 -> {chat_id}")
        await log_event(context.bot, f"⚙️ <b>内容模板移除</b>\n频道: <code>{chat_id}</code>", category="config")
    except Exception as e:
        logger.error(f"Error in handle_deltemplate: {e}")


@admin_only
async def handle_setfilter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set allowed media types for a chat."""
    if not update.message or len(context.args or []) < 2:
        await update.message.reply_text(
            "❌ 用法: `/setfilter -100xxx <类型1,类型2...>`\n可选: `photo, video, animation, document, audio, voice, sticker`",
            parse_mode="Markdown",
        )
        return
    chat_id = context.args[0]
    types = [t.strip().lower() for t in context.args[1].split(",") if t.strip()]
    if not await check_chat_permission(update.message.from_user.id, chat_id, context):
        await update.message.reply_text(get_text("no_permission"))
        return
    try:
        await ChatRepository.set_media_filter(chat_id, types)
        await reply_success(update.message, context, f"✅ 媒体过滤已设置: {', '.join(types)}", chat_id)
        logger.info(f"⚙️ [设置] 媒体过滤已更新 -> {chat_id} ({types})")
        await log_event(
            context.bot,
            f"⚙️ <b>媒体过滤变更</b>\n频道: <code>{chat_id}</code>\n允许类型: <code>{', '.join(types)}</code>",
            category="config",
        )
    except Exception as e:
        logger.error(f"Error in handle_setfilter: {e}")
