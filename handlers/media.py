#media.py
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from db import (
    has_seen, add_seen, save_chat, is_locked, inc_stat,
    get_forward_targets, has_forward_seen, add_forward_seen,
    has_album_forwarded, mark_album_forwarded
)
from cleaner import clean_caption

album_cache = {}

async def safe_send_media_group(bot, chat_id, media):
    for attempt in range(2):
        try:
            await bot.send_media_group(chat_id=chat_id, media=media)
            return True
        except Exception as e:
            print(f"[警告] 向 {chat_id} 转发相册失败: {e}")
            await asyncio.sleep(1)
    return False

async def safe_send_photo(bot, chat_id, file_id, caption):
    for attempt in range(2):
        try:
            await bot.send_photo(chat_id=chat_id, photo=file_id, caption=caption)
            return True
        except Exception as e:
            print(f"[警告] 向 {chat_id} 转发图片失败: {e}")
            await asyncio.sleep(1)
    return False

async def safe_send_video(bot, chat_id, file_id, caption):
    for attempt in range(2):
        try:
            await bot.send_video(chat_id=chat_id, video=file_id, caption=caption)
            return True
        except Exception as e:
            print(f"[警告] 向 {chat_id} 转发视频失败: {e}")
            await asyncio.sleep(1)
    return False

async def process_album(context, gid, chat_id):
    await asyncio.sleep(3)

    group = album_cache.pop(gid, None)
    if not group:
        return
    msgs = group["messages"]
    cleaned_caption = clean_caption(msgs[0].caption or None, str(chat_id))
    media = []
    for i, m in enumerate(msgs):
        cap = cleaned_caption if i == 0 else None
        if m.photo:
            media.append(InputMediaPhoto(m.photo[-1].file_id, caption=cap))
        elif m.video:
            media.append(InputMediaVideo(m.video.file_id, caption=cap))
        try:
            await m.delete()
        except Exception as e:
            print(f"[警告] 删除消息失败: {e}")
    try:
        await context.bot.send_media_group(chat_id=chat_id, media=media)
    except Exception as e:
        print(f"[警告] 发送相册失败: {e}")

    for tgt in get_forward_targets(str(chat_id)):
        cleaned_tgt = clean_caption(msgs[0].caption or None, str(tgt))
        media_tgt = []
        for i, m in enumerate(msgs):
            cap = cleaned_tgt if i == 0 else None
            if m.photo:
                media_tgt.append(InputMediaPhoto(m.photo[-1].file_id, caption=cap))
            elif m.video:
                media_tgt.append(InputMediaVideo(m.video.file_id, caption=cap))
        try:
            sent_msgs = await context.bot.send_media_group(chat_id=tgt, media=media_tgt)
            for m in sent_msgs:
                fid = m.video.file_unique_id if m.video else m.photo[-1].file_unique_id if m.photo else None
                if fid and has_forward_seen(tgt, fid):
                    try:
                        await m.delete()
                        print(f"[去重] 删除目标频道 {tgt} 的重复媒体")
                    except Exception as e:
                        print(f"[警告] 删除目标频道重复媒体失败: {e}")
                else:
                    if fid:
                        add_forward_seen(tgt, fid)
        except Exception as e:
            print(f"[警告] 向目标频道 {tgt} 转发相册失败: {e}")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.channel_post
    if not msg:
        return

    chat_id = str(msg.chat_id)
    if is_locked(chat_id):
        return

    save_chat(chat_id, msg.chat.title or "")
    fid = msg.video.file_unique_id if msg.video else msg.photo[-1].file_unique_id if msg.photo else None
    if not fid:
        return

    if has_seen(chat_id, fid):
        return  # 不删除重复消息，只跳过处理
    add_seen(chat_id, fid)
    inc_stat(chat_id)

    cleaned_caption = clean_caption(msg.caption or "", chat_id)

    # 修改原消息说明（如果清理后仍有内容且不同）
    if cleaned_caption and cleaned_caption != (msg.caption or "").strip():
        try:
            await context.bot.edit_message_caption(
                chat_id=msg.chat_id,
                message_id=msg.message_id,
                caption=cleaned_caption
            )
        except Exception as e:
            print(f"[警告] 修改说明失败: {e}")

    # 相册处理缓存（保留结构，不重发）
    if msg.media_group_id:
        g = album_cache.setdefault(msg.media_group_id, {"messages": []})
        g["messages"].append(msg)
        return  # 不再重发相册，保留原始结构

    # 转发到目标频道（保持原逻辑）
    for tgt in get_forward_targets(chat_id):
        cleaned_tgt = clean_caption(msg.caption or "", tgt)
        if not cleaned_tgt:
            continue

        try:
            if msg.photo:
                sent = await context.bot.send_photo(chat_id=tgt, photo=msg.photo[-1].file_id, caption=cleaned_tgt)
                fid_tgt = msg.photo[-1].file_unique_id
            elif msg.video:
                sent = await context.bot.send_video(chat_id=tgt, video=msg.video.file_id, caption=cleaned_tgt)
                fid_tgt = msg.video.file_unique_id
            else:
                continue

            if has_forward_seen(tgt, fid_tgt):
                try:
                    await sent.delete()
                    print(f"[去重] 删除目标频道 {tgt} 的重复媒体")
                except Exception as e:
                    print(f"[警告] 删除目标频道重复媒体失败: {e}")
            else:
                add_forward_seen(tgt, fid_tgt)

        except Exception as e:
            print(f"[警告] 向目标频道 {tgt} 转发失败: {e}")