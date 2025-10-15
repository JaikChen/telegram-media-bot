# handlers/media.py
# 处理群组和频道中的媒体消息（照片、视频），自动清理说明文字并重新发送

import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from db import has_seen, add_seen, save_chat, is_locked, inc_stat
from cleaner import clean_caption

# 相册缓存，用于收集 media_group 中的多张图片或视频
album_cache = {}

# 处理相册（多媒体消息组），清理说明并重新发送
async def process_album(context, gid, chat_id):
    await asyncio.sleep(1.5)  # 等待相册收集完成
    group = album_cache.pop(gid, None)
    if not group: return
    msgs = group["messages"]
    cleaned_caption = clean_caption(msgs[0].caption or None, str(chat_id))
    media = []
    for i, m in enumerate(msgs):
        cap_to_use = cleaned_caption if i == 0 else None
        if m.photo:
            media.append(InputMediaPhoto(m.photo[-1].file_id, caption=cap_to_use))
        elif m.video:
            media.append(InputMediaVideo(m.video.file_id, caption=cap_to_use))
    for m in msgs:
        await m.delete()
    await context.bot.send_media_group(chat_id=chat_id, media=media)

# 主处理器：处理单张媒体或相册，执行清理逻辑
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.channel_post
    if not msg: return
    chat_id = str(msg.chat_id)

    # 如果频道已锁定，跳过处理
    if is_locked(chat_id): return

    # 保存频道名称（用于展示）
    save_chat(chat_id, msg.chat.title or "")

    # 获取媒体唯一 ID（用于去重）
    fid = msg.video.file_unique_id if msg.video else msg.photo[-1].file_unique_id if msg.photo else None
    if not fid: return

    # 如果已处理过该媒体，直接删除
    if has_seen(chat_id, fid):
        await msg.delete(); return

    # 标记为已处理，并增加统计
    add_seen(chat_id, fid); inc_stat(chat_id)

    # 如果是相册消息，缓存并延迟处理
    if msg.media_group_id:
        g = album_cache.setdefault(msg.media_group_id, {"messages": [], "task": None})
        g["messages"].append(msg)
        if not g["task"]:
            g["task"] = asyncio.create_task(process_album(context, msg.media_group_id, msg.chat_id))
    else:
        # 单张媒体：清理说明并重新发送
        cleaned_caption = clean_caption(msg.caption or None, chat_id)
        await msg.delete()
        if msg.photo:
            await context.bot.send_photo(chat_id=msg.chat_id, photo=msg.photo[-1].file_id, caption=cleaned_caption)
        elif msg.video:
            await context.bot.send_video(chat_id=msg.chat_id, video=msg.video.file_id, caption=cleaned_caption)