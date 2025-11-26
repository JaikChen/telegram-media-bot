# handlers/media.py
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from db import *
from cleaner import clean_caption
from handlers.callback import get_vote_markup

album_cache = {}


async def log_event(bot, text):
    lc = get_log_channel()
    if lc:
        try:
            await bot.send_message(lc, text)
        except:
            pass


async def process_album(context, gid, chat_id):
    await asyncio.sleep(6)
    group = album_cache.pop(gid, None)
    if not group: return
    msgs = group["messages"]
    uid = msgs[0].from_user.id if msgs[0].from_user else None

    cleaned = clean_caption(msgs[0].caption or "", str(chat_id), uid, msgs[0].caption_entities)
    media = []
    for i, m in enumerate(msgs):
        cap = cleaned if i == 0 else None
        if m.photo:
            media.append(InputMediaPhoto(m.photo[-1].file_id, caption=cap))
        elif m.video:
            media.append(InputMediaVideo(m.video.file_id, caption=cap))
        try:
            await m.delete()
        except:
            pass

    try:
        await context.bot.send_media_group(chat_id=chat_id, media=media)
    except Exception as e:
        await log_event(context.bot, f"⚠️ 相册重发失败: {e} ({chat_id})")

    for tgt in get_forward_targets(str(chat_id)):
        if has_album_forwarded(str(chat_id), gid, str(tgt)): continue
        cl_tgt = clean_caption(msgs[0].caption or "", str(tgt))
        m_tgt = []
        for i, m in enumerate(msgs):
            cap = cl_tgt if i == 0 else None
            if m.photo:
                m_tgt.append(InputMediaPhoto(m.photo[-1].file_id, caption=cap))
            elif m.video:
                m_tgt.append(InputMediaVideo(m.video.file_id, caption=cap))
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
        except Exception as e:
            await log_event(context.bot, f"⚠️ 相册转发失败 {tgt}: {e}")


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
            await msg.delete(); await log_event(context.bot, f"🗑 重复删除: {chat_id}")
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

    uid = msg.from_user.id if msg.from_user else None
    cleaned = clean_caption(msg.caption or "", chat_id, uid, msg.caption_entities)

    try:
        await msg.delete()
    except:
        await log_event(context.bot, f"⚠️ 无法删除原消息: {chat_id}")

    markup = get_vote_markup(0, 0) if is_voting_enabled(chat_id) else None

    try:
        if msg.photo:
            await context.bot.send_photo(chat_id, msg.photo[-1].file_id, caption=cleaned, reply_markup=markup)
        elif msg.video:
            await context.bot.send_video(chat_id, msg.video.file_id, caption=cleaned, reply_markup=markup)
    except Exception as e:
        await log_event(context.bot, f"⚠️ 重发失败: {e}")

    for tgt in get_forward_targets(chat_id):
        cl_tgt = clean_caption(msg.caption or "", tgt)
        tm = get_vote_markup(0, 0) if is_voting_enabled(tgt) else None
        try:
            sent = None
            if msg.photo:
                sent = await context.bot.send_photo(tgt, msg.photo[-1].file_id, caption=cl_tgt, reply_markup=tm)
            elif msg.video:
                sent = await context.bot.send_video(tgt, msg.video.file_id, caption=cl_tgt, reply_markup=tm)

            if sent:
                fid_t = sent.photo[-1].file_unique_id if sent.photo else sent.video.file_unique_id
                if has_forward_seen(tgt, fid_t):
                    try:
                        await sent.delete()
                    except:
                        pass
                else:
                    add_forward_seen(tgt, fid_t)
        except Exception as e:
            await log_event(context.bot, f"⚠️ 转发失败 {tgt}: {e}")