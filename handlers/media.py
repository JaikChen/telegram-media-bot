# handlers/media.py
# 媒体消息处理器：核心逻辑（去重、清理、转发、相册合并、自动剧透）

import asyncio
import random
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from db import (
    has_seen, add_seen, save_chat, is_locked, inc_stat,
    get_forward_targets, has_forward_seen, add_forward_seen,
    has_album_forwarded, mark_album_forwarded, is_voting_enabled,
    enqueue_forward, peek_forward_queue, pop_forward_single, pop_forward_group,
    get_delay_settings
)
from cleaner import clean_caption, check_spoiler_tags, restore_all_tags
from handlers.callback import get_vote_markup
from handlers.utils import log_event

album_cache = {}


# --- 队列处理 Worker ---
async def forward_worker(context: ContextTypes.DEFAULT_TYPE):
    """后台任务：处理转发队列"""
    row = peek_forward_queue()
    if not row:
        return

    row_id, target_id, media_type, file_id, caption, has_spoiler, file_unique_id, group_id, _ = row

    try:
        # 如果是相册
        if group_id:
            group_rows = pop_forward_group(target_id, group_id)
            if group_rows:
                media_group = []
                for gr in group_rows:
                    if gr[2] == 'photo':
                        media_group.append(InputMediaPhoto(gr[3], caption=gr[4], has_spoiler=bool(gr[5])))
                    elif gr[2] == 'video':
                        media_group.append(InputMediaVideo(gr[3], caption=gr[4], has_spoiler=bool(gr[5])))

                if media_group:
                    sent_msgs = await context.bot.send_media_group(chat_id=target_id, media=media_group)
                    for m in sent_msgs:
                        fid = m.video.file_unique_id if m.video else m.photo[-1].file_unique_id if m.photo else None
                        if fid:
                            add_forward_seen(target_id, fid)

                    await log_event(context.bot, f"延迟转发相册到 `{target_id}`", category="forward")

        # 如果是单条消息
        else:
            markup = get_vote_markup(0, 0) if is_voting_enabled(target_id) else None
            sent = None
            if media_type == 'photo':
                sent = await context.bot.send_photo(target_id, file_id, caption=caption, reply_markup=markup,
                                                    has_spoiler=bool(has_spoiler))
            elif media_type == 'video':
                sent = await context.bot.send_video(target_id, file_id, caption=caption, reply_markup=markup,
                                                    has_spoiler=bool(has_spoiler))

            if sent:
                if file_unique_id:
                    add_forward_seen(target_id, file_unique_id)
                await log_event(context.bot, f"延迟转发到 `{target_id}`", category="forward")

            pop_forward_single(row_id)

    except Exception as e:
        await log_event(context.bot, f"延迟转发失败 (删除任务): {e}", category="error")
        if group_id:
            pop_forward_group(target_id, group_id)
        else:
            pop_forward_single(row_id)

    # 调度下一次运行
    min_s, max_s = get_delay_settings()
    if peek_forward_queue():
        delay = 0
        if max_s > 0:
            delay = random.randint(min_s, max_s)

        # 再次检查 job_queue 是否存在
        if context.job_queue:
            context.job_queue.run_once(forward_worker, delay)


# --------------------------------

async def process_album(context, gid, chat_id):
    await asyncio.sleep(6)
    group = album_cache.pop(gid, None)
    if not group: return
    msgs = group["messages"]

    uid = msgs[0].from_user.id if msgs[0].from_user else None
    original_caption = msgs[0].caption or ""
    entities = msgs[0].caption_entities

    has_spoiler = check_spoiler_tags(original_caption)
    cleaned = clean_caption(original_caption, str(chat_id), uid, entities)
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
        await log_event(context.bot, f"相册重发失败: {e}", category="error")

    # 转发逻辑
    min_s, max_s = get_delay_settings()
    # [关键修复] 只有当 max_s > 0 且 job_queue 可用时，才开启延迟模式
    # 否则即使设置了延迟，也强制走直接发送流程，防止消息积压
    is_delayed = (max_s > 0) and (context.job_queue is not None)

    for tgt in get_forward_targets(str(chat_id)):
        if has_album_forwarded(str(chat_id), gid, str(tgt)): continue

        cl_tgt = clean_caption(original_caption, str(tgt))
        cl_tgt = restore_all_tags(original_caption, cl_tgt)

        if is_delayed:
            for i, m in enumerate(msgs):
                cap = cl_tgt if i == 0 else None
                m_type = 'photo' if m.photo else 'video'
                f_id = m.photo[-1].file_id if m.photo else m.video.file_id
                enqueue_forward(tgt, m_type, f_id, cap, has_spoiler, None, gid)

            mark_album_forwarded(str(chat_id), gid, str(tgt))

            if context.job_queue and len(context.job_queue.get_jobs_by_name("forward_worker")) == 0:
                context.job_queue.run_once(forward_worker, 1, name="forward_worker")

        else:
            # 实时转发 (降级模式)
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
                    if fid: add_forward_seen(tgt, fid)
                mark_album_forwarded(str(chat_id), gid, str(tgt))
                await log_event(context.bot, f"转发相册到 `{tgt}`", category="forward")
            except Exception as e:
                await log_event(context.bot, f"转发失败: {e}", category="error")


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
            await log_event(context.bot, f"重复删除: {chat_id}", category="duplicate")
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
    original_caption = msg.caption or ""

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
            await log_event(context.bot, f"已清理: {chat_id}", category="clean")
    except Exception as e:
        await log_event(context.bot, f"重发失败: {e}", category="error")

    min_s, max_s = get_delay_settings()
    # [关键修复] 如果 job_queue 不存在，强制 is_delayed = False
    is_delayed = (max_s > 0) and (context.job_queue is not None)

    for tgt in get_forward_targets(chat_id):
        cl_tgt = clean_caption(original_caption, tgt)
        cl_tgt = restore_all_tags(original_caption, cl_tgt)

        if is_delayed:
            m_type = 'photo' if msg.photo else 'video'
            f_id = msg.photo[-1].file_id if msg.photo else msg.video.file_id
            enqueue_forward(tgt, m_type, f_id, cl_tgt, has_spoiler, fid)

            if context.job_queue and len(context.job_queue.get_jobs_by_name("forward_worker")) == 0:
                context.job_queue.run_once(forward_worker, 1, name="forward_worker")

        else:
            # 实时转发
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

                await log_event(context.bot, f"转发到 `{tgt}`", category="forward")
            except Exception as e:
                await log_event(context.bot, f"转发失败 {tgt}: {e}", category="error")