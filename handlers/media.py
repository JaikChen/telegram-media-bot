# handlers/media.py
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from db import (
    has_seen, add_seen, save_chat, is_locked, inc_stat,
    get_forward_targets, has_forward_seen, add_forward_seen,
    has_album_forwarded, mark_album_forwarded, is_voting_enabled
)
# [修改] 导入新的辅助函数
from cleaner import clean_caption, check_spoiler_tags, restore_all_tags
from handlers.callback import get_vote_markup
from handlers.utils import log_event

album_cache = {}


async def process_album(context, gid, chat_id):
    await asyncio.sleep(6)
    group = album_cache.pop(gid, None)
    if not group: return
    msgs = group["messages"]

    uid = msgs[0].from_user.id if msgs[0].from_user else None
    original_caption = msgs[0].caption or ""
    entities = msgs[0].caption_entities

    # 1. 检查剧透 (调用 cleaner)
    has_spoiler = check_spoiler_tags(original_caption)

    # 2. 清理 (调用 cleaner)
    cleaned = clean_caption(original_caption, str(chat_id), uid, entities)

    # 3. 回填标签 (调用 cleaner)
    cleaned = restore_all_tags(original_caption, cleaned)

    media = []
    for i, m in enumerate(msgs):
        cap = cleaned if i == 0 else None
        if m.photo:
            media.append(InputMediaPhoto(m.photo[-1].file_id, caption=cap, has_spoiler=has_spoiler))
        elif m.video:
            media.append(InputMediaVideo(m.video.file_id, caption=cap, has_spoiler=has_spoiler))
        try:
            await m.delete()
        except:
            pass

    try:
        await context.bot.send_media_group(chat_id=chat_id, media=media)
    except Exception as e:
        await log_event(context.bot, f"相册重发失败: {e} ({chat_id})", category="error")

    for tgt in get_forward_targets(str(chat_id)):
        if has_album_forwarded(str(chat_id), gid, str(tgt)): continue

        cl_tgt = clean_caption(original_caption, str(tgt))
        cl_tgt = restore_all_tags(original_caption, cl_tgt)

        m_tgt = []
        for i, m in enumerate(msgs):
            cap = cl_tgt if i == 0 else None
            if m.photo:
                m_tgt.append(InputMediaPhoto(m.photo[-1].file_id, caption=cap, has_spoiler=has_spoiler))
            elif m.video:
                m_tgt.append(InputMediaVideo(m.video.file_id, caption=cap, has_spoiler=has_spoiler))
        try:
            sent = await context.bot.send_media_group(chat_id=tgt, media=m_tgt)
            for m in sent:
                fid = m.video.file_unique_id if m.video else m.photo[-1].file_unique_id if m.photo else None
                if fid and has_forward_seen(tgt, fid):
                    try:
                        await m.delete()
                    except:
                        pass
                elif fid:
                    add_forward_seen(tgt, fid)
            mark_album_forwarded(str(chat_id), gid, str(tgt))
            await log_event(context.bot, f"相册从 `{chat_id}` 转发到 `{tgt}`", category="forward")
        except Exception as e:
            await log_event(context.bot, f"相册转发失败 {tgt}: {e}", category="error")


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.channel_post
    if not msg: return
    chat_id = str(msg.chat_id)
    if is_locked(chat_id): return

    save_chat(chat_id, msg.chat.title or "")
    fid = msg.video.file_unique_id if msg.video else msg.photo[-1].file_unique_id if msg.photo else None
    if not fid: return

    if has_seen(chat_id, fid):
        try:
            await msg.delete()
            await log_event(context.bot, f"频道 `{chat_id}` 发现重复媒体，已自动删除。", category="duplicate")
        except:
            pass
        return
    add_seen(chat_id, fid)
    inc_stat(chat_id)

    if msg.media_group_id:
        g = album_cache.setdefault(msg.media_group_id, {"messages": []})
        g["messages"].append(msg)
        asyncio.create_task(process_album(context, msg.media_group_id, msg.chat_id))
        return

    original_caption = msg.caption or ""
    uid = msg.from_user.id if msg.from_user else None

    # 调用 cleaner 中的函数
    has_spoiler = check_spoiler_tags(original_caption)
    cleaned = clean_caption(original_caption, chat_id, uid, msg.caption_entities)
    cleaned = restore_all_tags(original_caption, cleaned)

    try:
        await msg.delete()
    except:
        await log_event(context.bot, f"无法删除原消息: {chat_id}", category="error")

    markup = get_vote_markup(0, 0) if is_voting_enabled(chat_id) else None

    try:
        if msg.photo:
            await context.bot.send_photo(chat_id, msg.photo[-1].file_id, caption=cleaned, reply_markup=markup,
                                         has_spoiler=has_spoiler)
        elif msg.video:
            await context.bot.send_video(chat_id, msg.video.file_id, caption=cleaned, reply_markup=markup,
                                         has_spoiler=has_spoiler)

        if cleaned != original_caption:
            await log_event(context.bot, f"频道 `{chat_id}` 单条媒体说明已清理。", category="clean")
    except Exception as e:
        await log_event(context.bot, f"重发失败: {e}", category="error")

    for tgt in get_forward_targets(chat_id):
        cl_tgt = clean_caption(original_caption, tgt)
        cl_tgt = restore_all_tags(original_caption, cl_tgt)
        tm = get_vote_markup(0, 0) if is_voting_enabled(tgt) else None
        try:
            sent = None
            if msg.photo:
                sent = await context.bot.send_photo(tgt, msg.photo[-1].file_id, caption=cl_tgt, reply_markup=tm,
                                                    has_spoiler=has_spoiler)
            elif msg.video:
                sent = await context.bot.send_video(tgt, msg.video.file_id, caption=cl_tgt, reply_markup=tm,
                                                    has_spoiler=has_spoiler)

            if sent:
                fid_t = sent.photo[-1].file_unique_id if sent.photo else sent.video.file_unique_id
                if has_forward_seen(tgt, fid_t):
                    try:
                        await sent.delete()
                    except:
                        pass
                else:
                    add_forward_seen(tgt, fid_t)
            await log_event(context.bot, f"从 `{chat_id}` 转发到 `{tgt}`", category="forward")
        except Exception as e:
            await log_event(context.bot, f"转发失败 {tgt}: {e}", category="error")