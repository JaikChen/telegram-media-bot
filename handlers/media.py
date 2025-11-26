# handlers/media.py
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from db import (
    has_seen, add_seen, save_chat, is_locked, inc_stat,
    get_forward_targets, has_forward_seen, add_forward_seen,
    has_album_forwarded, mark_album_forwarded, get_log_channel,
    is_voting_enabled  # [新增]
)
from cleaner import clean_caption
from handlers.callback import get_vote_markup  # [新增]

album_cache = {}


async def log_event(bot, text: str):
    log_channel = get_log_channel()
    if log_channel:
        try:
            await bot.send_message(chat_id=log_channel, text=text)
        except Exception:
            pass


async def process_album(context, gid, chat_id):
    await asyncio.sleep(6)

    group = album_cache.pop(gid, None)
    if not group:
        return

    msgs = group["messages"]
    chat_title = msgs[0].chat.title or str(chat_id)

    user_id = msgs[0].from_user.id if msgs[0].from_user else None
    cleaned_caption = clean_caption(msgs[0].caption or "", str(chat_id), user_id)

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
            print(f"[警告] 删除原始相册消息失败: {e}")

    if cleaned_caption != (msgs[0].caption or ""):
        await log_event(context.bot,
                        f"♻️ [相册清理] 频道 `{chat_title}` ({chat_id})\n已清理 {len(msgs)} 条媒体的说明文字。")

    try:
        # 相册不支持直接带按钮，故暂不添加 reply_markup
        await context.bot.send_media_group(chat_id=chat_id, media=media)
    except Exception as e:
        err_msg = f"⚠️ [警告] 重发相册失败: {e}\n频道: {chat_title} ({chat_id})"
        print(err_msg)
        await log_event(context.bot, err_msg)

    for tgt in get_forward_targets(str(chat_id)):
        if has_album_forwarded(str(chat_id), gid, str(tgt)):
            continue

        cleaned_tgt = clean_caption(msgs[0].caption or "", str(tgt))
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
                    except Exception:
                        pass
                else:
                    if fid:
                        add_forward_seen(tgt, fid)
            mark_album_forwarded(str(chat_id), gid, str(tgt))
            await log_event(context.bot, f"↪️ [相册转发] 从 `{chat_title}` 转发到 `{tgt}`")
        except Exception as e:
            print(f"[警告] 向目标频道 {tgt} 转发相册失败: {e}")
            await log_event(context.bot, f"⚠️ [转发失败] 目标: {tgt}\n错误: {e}")


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.channel_post
    if not msg:
        return

    chat_id = str(msg.chat_id)
    chat_title = msg.chat.title or chat_id

    if is_locked(chat_id):
        return

    save_chat(chat_id, msg.chat.title or "")
    fid = msg.video.file_unique_id if msg.video else msg.photo[-1].file_unique_id if msg.photo else None
    if not fid:
        return

    if has_seen(chat_id, fid):
        try:
            await msg.delete()
            await log_event(context.bot, f"🗑 [去重] 频道 `{chat_title}` ({chat_id})\n发现重复媒体，已自动删除。")
        except Exception as e:
            print(f"[警告] 删除重复消息失败: {e}")
        return
    add_seen(chat_id, fid)
    inc_stat(chat_id)

    if msg.media_group_id:
        g = album_cache.setdefault(msg.media_group_id, {"messages": []})
        g["messages"].append(msg)
        asyncio.create_task(process_album(context, msg.media_group_id, msg.chat_id))
        return

    original_caption = msg.caption or ""
    user_id = msg.from_user.id if msg.from_user else None
    cleaned_caption = clean_caption(original_caption, chat_id, user_id)

    try:
        await msg.delete()
    except Exception as e:
        print(f"[警告] 删除原始消息失败: {e}")
        await log_event(context.bot, f"⚠️ [权限不足] 无法删除原始消息\n频道: {chat_title}")

    # [修改] 检查是否开启投票
    reply_markup = get_vote_markup(0, 0) if is_voting_enabled(chat_id) else None

    try:
        if msg.photo:
            sent = await context.bot.send_photo(
                chat_id=chat_id,
                photo=msg.photo[-1].file_id,
                caption=cleaned_caption or None,
                reply_markup=reply_markup  # 附加按钮
            )
        elif msg.video:
            sent = await context.bot.send_video(
                chat_id=chat_id,
                video=msg.video.file_id,
                caption=cleaned_caption or None,
                reply_markup=reply_markup  # 附加按钮
            )
        else:
            return

        if cleaned_caption != original_caption:
            await log_event(context.bot, f"♻️ [清理] 频道 `{chat_title}` ({chat_id})\n已处理媒体说明。")

    except Exception as e:
        err_msg = f"⚠️ [重发失败] 频道: {chat_title}\n错误: {e}"
        print(err_msg)
        await log_event(context.bot, err_msg)
        return

    for tgt in get_forward_targets(chat_id):
        cleaned_tgt = clean_caption(msg.caption or "", tgt)

        # [修改] 目标频道也检查是否开启投票
        tgt_markup = get_vote_markup(0, 0) if is_voting_enabled(tgt) else None

        try:
            if msg.photo:
                sent_tgt = await context.bot.send_photo(
                    chat_id=tgt,
                    photo=msg.photo[-1].file_id,
                    caption=cleaned_tgt or None,
                    reply_markup=tgt_markup
                )
                fid_tgt = sent_tgt.photo[-1].file_unique_id if sent_tgt.photo else None
            elif msg.video:
                sent_tgt = await context.bot.send_video(
                    chat_id=tgt,
                    video=msg.video.file_id,
                    caption=cleaned_tgt or None,
                    reply_markup=tgt_markup
                )
                fid_tgt = sent_tgt.video.file_unique_id if sent_tgt.video else None
            else:
                continue

            if fid_tgt and has_forward_seen(tgt, fid_tgt):
                try:
                    await sent_tgt.delete()
                except Exception:
                    pass
            else:
                if fid_tgt:
                    add_forward_seen(tgt, fid_tgt)

            await log_event(context.bot, f"↪️ [转发] 从 `{chat_title}` 转发到 `{tgt}`")

        except Exception as e:
            print(f"[警告] 向目标频道 {tgt} 转发失败: {e}")
            await log_event(context.bot, f"⚠️ [转发失败] 目标: {tgt}\n错误: {e}")