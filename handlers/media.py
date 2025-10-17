# handlers/media.py
# 处理群组和频道中的媒体消息（照片、视频），自动清理说明文字并重新发送，并支持转发

import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from db import has_seen, add_seen, save_chat, is_locked, inc_stat, get_forward_targets
from cleaner import clean_caption

# 相册缓存，用于收集 media_group 中的多张图片或视频
album_cache = {}

# 处理相册（多媒体消息组），清理说明并重新发送
async def process_album(context, gid, chat_id):
    await asyncio.sleep(2.5)  # 延迟等待，减少漏收
    group = album_cache.pop(gid, None)
    if not group:
        return
    msgs = group["messages"]

    # 清理说明（原频道）
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

    # 发送到原频道/群组
    try:
        await context.bot.send_media_group(chat_id=chat_id, media=media)
    except Exception as e:
        print(f"[警告] 发送相册失败: {e}")

    # 转发到目标频道（重新清理说明）
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
            await context.bot.send_media_group(chat_id=tgt, media=media_tgt)
        except Exception as e:
            print(f"[警告] 向 {tgt} 转发相册失败: {e}")

# 主处理器：处理单张媒体或相册
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.channel_post
    if not msg:
        return
    chat_id = str(msg.chat_id)

    # 如果频道已锁定，跳过处理
    if is_locked(chat_id):
        return

    # 保存频道名称
    save_chat(chat_id, msg.chat.title or "")

    # 获取媒体唯一 ID
    fid = msg.video.file_unique_id if msg.video else msg.photo[-1].file_unique_id if msg.photo else None
    if not fid:
        return

    # 去重：仅限同频道
    if has_seen(chat_id, fid):
        try:
            await msg.delete()
        except Exception as e:
            print(f"[警告] 删除消息失败: {e}")
        return

    # 标记已处理并统计
    add_seen(chat_id, fid)
    inc_stat(chat_id)

    # 相册处理
    if msg.media_group_id:
        g = album_cache.setdefault(msg.media_group_id, {"messages": [], "task": None})
        g["messages"].append(msg)
        if not g["task"]:
            g["task"] = asyncio.create_task(process_album(context, msg.media_group_id, msg.chat_id))
    else:
        # 单张媒体（原频道清理）
        cleaned_caption = clean_caption(msg.caption or None, chat_id)
        try:
            await msg.delete()
        except Exception as e:
            print(f"[警告] 删除消息失败: {e}")

        if msg.photo:
            try:
                await context.bot.send_photo(chat_id=msg.chat_id, photo=msg.photo[-1].file_id, caption=cleaned_caption)
            except Exception as e:
                print(f"[警告] 发送图片失败: {e}")
            # 转发（目标频道重新清理）
            for tgt in get_forward_targets(chat_id):
                cleaned_tgt = clean_caption(msg.caption or None, tgt)
                try:
                    await context.bot.send_photo(chat_id=tgt, photo=msg.photo[-1].file_id, caption=cleaned_tgt)
                except Exception as e:
                    print(f"[警告] 向 {tgt} 转发图片失败: {e}")

        elif msg.video:
            try:
                await context.bot.send_video(chat_id=msg.chat_id, video=msg.video.file_id, caption=cleaned_caption)
            except Exception as e:
                print(f"[警告] 发送视频失败: {e}")
            # 转发（目标频道重新清理）
            for tgt in get_forward_targets(chat_id):
                cleaned_tgt = clean_caption(msg.caption or None, tgt)
                try:
                    await context.bot.send_video(chat_id=tgt, video=msg.video.file_id, caption=cleaned_tgt)
                except Exception as e:
                    print(f"[警告] 向 {tgt} 转发视频失败: {e}")