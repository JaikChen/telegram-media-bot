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

# 相册缓存: media_group_id -> {messages: [], timer_task: Task}
album_cache = {}


async def forward_worker(context: ContextTypes.DEFAULT_TYPE):
    """后台任务：处理延迟转发队列"""
    row = peek_forward_queue()
    if not row: return

    row_id, target_id, media_type, file_id, caption, has_spoiler, file_unique_id, group_id, _ = row

    try:
        if group_id:
            # 相册处理
            group_rows = pop_forward_group(target_id, group_id)
            if group_rows:
                media = []
                for gr in group_rows:
                    m_type, f_id, cap, spoil = gr[2], gr[3], gr[4], bool(gr[5])
                    if m_type == 'photo':
                        media.append(InputMediaPhoto(f_id, caption=cap, has_spoiler=spoil))
                    elif m_type == 'video':
                        media.append(InputMediaVideo(f_id, caption=cap, has_spoiler=spoil))

                if media:
                    sent_msgs = await context.bot.send_media_group(chat_id=target_id, media=media)
                    # 记录发送过的 ID 避免回环
                    for m in sent_msgs:
                        fid = m.video.file_unique_id if m.video else m.photo[-1].file_unique_id if m.photo else None
                        if fid: add_forward_seen(target_id, fid)
                    await log_event(context.bot, f"延迟转发相册到 `{target_id}`", category="forward")
        else:
            # 单图/视频处理
            markup = get_vote_markup(0, 0) if is_voting_enabled(target_id) else None
            if media_type == 'photo':
                await context.bot.send_photo(target_id, file_id, caption=caption, reply_markup=markup,
                                             has_spoiler=bool(has_spoiler))
            elif media_type == 'video':
                await context.bot.send_video(target_id, file_id, caption=caption, reply_markup=markup,
                                             has_spoiler=bool(has_spoiler))

            if file_unique_id: add_forward_seen(target_id, file_unique_id)
            pop_forward_single(row_id)
            await log_event(context.bot, f"延迟转发到 `{target_id}`", category="forward")

    except Exception as e:
        await log_event(context.bot, f"延迟转发失败: {e}", category="error")
        # 即使失败也要移除队列，防止堵塞
        if group_id:
            pop_forward_group(target_id, group_id)
        else:
            pop_forward_single(row_id)

    # 循环调度
    min_s, max_s = get_delay_settings()
    if peek_forward_queue() and max_s > 0:
        delay = random.randint(min_s, max_s)
        context.job_queue.run_once(forward_worker, delay)


async def process_album(context: ContextTypes.DEFAULT_TYPE, gid: str, chat_id: str):
    """处理收集完成的相册"""
    await asyncio.sleep(4)  # 等待所有图片到达

    group_data = album_cache.pop(gid, None)
    if not group_data: return
    msgs = group_data["messages"]
    if not msgs: return

    # 取第一条消息的文案作为基准
    first_msg = msgs[0]
    uid = first_msg.from_user.id if first_msg.from_user else None
    original_caption = first_msg.caption or ""

    # 清理文案
    has_spoiler = check_spoiler_tags(original_caption)
    cleaned = clean_caption(original_caption, str(chat_id), uid, first_msg.caption_entities)
    cleaned = restore_all_tags(original_caption, cleaned)

    # 1. 本地重发 (清理后)
    media_list = []
    for i, m in enumerate(msgs):
        cap = cleaned if i == 0 else None  # 仅第一张带文案
        if m.photo:
            media_list.append(InputMediaPhoto(m.photo[-1].file_id, caption=cap, has_spoiler=has_spoiler))
        elif m.video:
            media_list.append(InputMediaVideo(m.video.file_id, caption=cap, has_spoiler=has_spoiler))
        # 尝试删除原消息
        try:
            await m.delete()
        except:
            pass

    try:
        await context.bot.send_media_group(chat_id=chat_id, media=media_list)
        if cleaned != original_caption:
            await log_event(context.bot, f"相册已清理: {chat_id}", category="clean")
    except Exception as e:
        await log_event(context.bot, f"相册重发失败: {e}", category="error")

    # 2. 转发逻辑
    min_s, max_s = get_delay_settings()
    use_queue = (max_s > 0) and (context.job_queue is not None)

    for tgt in get_forward_targets(str(chat_id)):
        if has_album_forwarded(str(chat_id), gid, tgt): continue

        # 针对目标频道的清理规则
        tgt_cap = clean_caption(original_caption, tgt)
        tgt_cap = restore_all_tags(original_caption, tgt_cap)

        if use_queue:
            # 入队
            for i, m in enumerate(msgs):
                cap = tgt_cap if i == 0 else None
                m_type = 'photo' if m.photo else 'video'
                f_id = m.photo[-1].file_id if m.photo else m.video.file_id
                enqueue_forward(tgt, m_type, f_id, cap, has_spoiler, None, gid)

            mark_album_forwarded(str(chat_id), gid, tgt)
            # 触发 Worker
            if not context.job_queue.get_jobs_by_name("forward_worker"):
                context.job_queue.run_once(forward_worker, 1, name="forward_worker")
        else:
            # 实时转发
            tgt_media = []
            for i, m in enumerate(msgs):
                cap = tgt_cap if i == 0 else None
                if m.photo:
                    tgt_media.append(InputMediaPhoto(m.photo[-1].file_id, caption=cap, has_spoiler=has_spoiler))
                elif m.video:
                    tgt_media.append(InputMediaVideo(m.video.file_id, caption=cap, has_spoiler=has_spoiler))

            try:
                sent = await context.bot.send_media_group(tgt, tgt_media)
                for m in sent:
                    fid = m.video.file_unique_id if m.video else m.photo[-1].file_unique_id if m.photo else None
                    if fid: add_forward_seen(tgt, fid)
                mark_album_forwarded(str(chat_id), gid, tgt)
            except Exception as e:
                await log_event(context.bot, f"相册转发失败 {tgt}: {e}", category="error")


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.channel_post
    if not msg: return

    chat_id = str(msg.chat_id)
    if is_locked(chat_id): return
    save_chat(chat_id, msg.chat.title or "")

    # 获取文件指纹用于去重
    fid = None
    if msg.video:
        fid = msg.video.file_unique_id
    elif msg.photo:
        fid = msg.photo[-1].file_unique_id

    if not fid: return  # 不处理非媒体

    # 去重检查
    if has_seen(chat_id, fid):
        try:
            await msg.delete(); await log_event(context.bot, f"去重删除: {chat_id}", category="duplicate")
        except:
            pass
        return

    add_seen(chat_id, fid)
    inc_stat(chat_id)

    # --- 相册模式 ---
    if msg.media_group_id:
        gid = msg.media_group_id
        if gid not in album_cache:
            album_cache[gid] = {"messages": []}
            # 启动一个异步任务等待收集
            context.application.create_task(process_album(context, gid, chat_id))
        album_cache[gid]["messages"].append(msg)
        return

    # --- 单条模式 ---
    uid = msg.from_user.id if msg.from_user else None
    original_caption = msg.caption or ""
    has_spoiler = check_spoiler_tags(original_caption)

    # 清理
    cleaned = clean_caption(original_caption, chat_id, uid, msg.caption_entities)
    cleaned = restore_all_tags(original_caption, cleaned)

    try:
        await msg.delete()
    except:
        pass

    # 重发
    markup = get_vote_markup(0, 0) if is_voting_enabled(chat_id) else None
    try:
        if msg.photo:
            await context.bot.send_photo(chat_id, msg.photo[-1].file_id, caption=cleaned, reply_markup=markup,
                                         has_spoiler=has_spoiler)
        elif msg.video:
            await context.bot.send_video(chat_id, msg.video.file_id, caption=cleaned, reply_markup=markup,
                                         has_spoiler=has_spoiler)
    except Exception as e:
        await log_event(context.bot, f"重发失败: {e}", category="error")

    # 转发
    min_s, max_s = get_delay_settings()
    use_queue = (max_s > 0) and (context.job_queue is not None)

    for tgt in get_forward_targets(chat_id):
        tgt_cap = clean_caption(original_caption, tgt)
        tgt_cap = restore_all_tags(original_caption, tgt_cap)

        if use_queue:
            m_type = 'photo' if msg.photo else 'video'
            f_id = msg.photo[-1].file_id if msg.photo else msg.video.file_id
            enqueue_forward(tgt, m_type, f_id, tgt_cap, has_spoiler, fid)

            if not context.job_queue.get_jobs_by_name("forward_worker"):
                context.job_queue.run_once(forward_worker, 1, name="forward_worker")
        else:
            try:
                tm = get_vote_markup(0, 0) if is_voting_enabled(tgt) else None
                sent = None
                if msg.photo:
                    sent = await context.bot.send_photo(tgt, msg.photo[-1].file_id, caption=tgt_cap, reply_markup=tm,
                                                        has_spoiler=has_spoiler)
                elif msg.video:
                    sent = await context.bot.send_video(tgt, msg.video.file_id, caption=tgt_cap, reply_markup=tm,
                                                        has_spoiler=has_spoiler)

                if sent:
                    fid_t = sent.photo[-1].file_unique_id if sent.photo else sent.video.file_unique_id
                    add_forward_seen(tgt, fid_t)
                await log_event(context.bot, f"转发到 `{tgt}`", category="forward")
            except Exception as e:
                await log_event(context.bot, f"转发失败 {tgt}: {e}", category="error")