# main.py
# 程序入口：初始化数据库，注册命令和消息处理器，启动 Bot

import logging
from datetime import time
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, AIORateLimiter
from config import BOT_TOKEN
from db import (
    init_db, clean_expired_data, vacuum_db, init_db_connection, close_db_connection,
    peek_forward_queue  # [新增] 用于检查是否有积压
)

# 导入各模块 Handler
from handlers.media import handle_media, forward_worker  # [新增] 导入转发Worker
from handlers.callback import handle_vote_callback
from handlers.message import handle_text_message

from handlers.sys_admin import (
    handle_addadmin, handle_deladmin, handle_listadmins,
    handle_backupdb, handle_restoredb,
    handle_setlog, handle_dellog, handle_setlogfilter,
    handle_cleanchats, handle_cleandb, handle_leave,
    handle_setdelay
)

from handlers.chat_mgmt import (
    handle_setrules, handle_addrule, handle_delrule, handle_listrules, handle_clearrules,
    handle_preview,
    handle_addkw, handle_listkw, handle_delkw,
    handle_addreplace, handle_delreplace, handle_listreplace,
    handle_setfooter, handle_delfooter,
    handle_lock, handle_unlock,
    handle_addforward, handle_delforward, handle_listforward,
    handle_allowuser, handle_blockuser, handle_listallowed,
    handle_setquiet, handle_setvoting,
    handle_addtrigger, handle_deltrigger, handle_listtriggers
)

from handlers.info import (
    handle_listchats, handle_chatinfo, handle_stats, handle_help, handle_queue_status
)

# ----------------------------------------------------
# 日志配置
# ----------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
# 屏蔽 httpx 和 aiosqlite 的详细日志，避免刷屏
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)


# ----------------------------------------------------
# 定时维护任务
# ----------------------------------------------------
async def daily_maintenance(context):
    print("⏳ [System] 执行每日维护任务...")
    # 清理 365 天前的过期数据
    deleted = await clean_expired_data(days=365)
    # 整理数据库文件碎片
    await vacuum_db()
    print(f"✅ [System] 维护完成，清理了 {deleted} 条过期记录。")


async def post_init(application):
    """启动前初始化"""
    print("⏳ [System] 正在初始化数据库连接...")
    await init_db_connection()
    await init_db()
    print("✅ [System] 数据库就绪。")

    # [新增] 启动时检查是否有中断的转发任务
    print("🔍 [System] 检查积压转发队列...")
    if await peek_forward_queue():
        print("🔄 [System] 发现未完成的转发任务，正在恢复转发队列...")
        # 立即启动 Worker，延时 1 秒给 Bot 缓冲时间
        application.job_queue.run_once(forward_worker, 1, name="forward_worker")
    else:
        print("✅ [System] 转发队列为空。")


async def post_shutdown(application):
    """关闭时清理"""
    print("🔌 [System] 正在关闭数据库连接...")
    await close_db_connection()


def main():
    # 2. 构建 Bot 应用
    # 启用 AIORateLimiter 防止 429 错误
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .rate_limiter(AIORateLimiter(overall_max_rate=30, overall_time_period=1))
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # =========================
    # 注册命令处理器 (Handlers)
    # =========================

    # --- 系统管理 (System Admin) ---
    app.add_handler(CommandHandler("addadmin", handle_addadmin))
    app.add_handler(CommandHandler("deladmin", handle_deladmin))
    app.add_handler(CommandHandler("listadmins", handle_listadmins))
    app.add_handler(CommandHandler("backupdb", handle_backupdb))
    app.add_handler(CommandHandler("restoredb", handle_restoredb))

    # 日志相关
    app.add_handler(CommandHandler("setlog", handle_setlog))
    app.add_handler(CommandHandler("setlogfilter", handle_setlogfilter))
    app.add_handler(CommandHandler("dellog", handle_dellog))

    # 维护相关
    app.add_handler(CommandHandler("cleanchats", handle_cleanchats))
    app.add_handler(CommandHandler("cleandb", handle_cleandb))
    app.add_handler(CommandHandler("leave", handle_leave))
    app.add_handler(CommandHandler("setdelay", handle_setdelay))

    # --- 群组管理 (Chat Management) ---
    # 规则
    app.add_handler(CommandHandler("setrules", handle_setrules))
    app.add_handler(CommandHandler("addrule", handle_addrule))
    app.add_handler(CommandHandler("delrule", handle_delrule))
    app.add_handler(CommandHandler("listrules", handle_listrules))
    app.add_handler(CommandHandler("clearrules", handle_clearrules))

    # 关键词
    app.add_handler(CommandHandler("addkw", handle_addkw))
    app.add_handler(CommandHandler("listkw", handle_listkw))
    app.add_handler(CommandHandler("delkw", handle_delkw))

    # 替换
    app.add_handler(CommandHandler("addreplace", handle_addreplace))
    app.add_handler(CommandHandler("delreplace", handle_delreplace))
    app.add_handler(CommandHandler("listreplace", handle_listreplace))

    # 页脚 & 白名单
    app.add_handler(CommandHandler("setfooter", handle_setfooter))
    app.add_handler(CommandHandler("delfooter", handle_delfooter))
    app.add_handler(CommandHandler("allowuser", handle_allowuser))
    app.add_handler(CommandHandler("blockuser", handle_blockuser))
    app.add_handler(CommandHandler("listallowed", handle_listallowed))

    # 转发与锁定
    app.add_handler(CommandHandler("lock", handle_lock))
    app.add_handler(CommandHandler("unlock", handle_unlock))
    app.add_handler(CommandHandler("addforward", handle_addforward))
    app.add_handler(CommandHandler("delforward", handle_delforward))
    app.add_handler(CommandHandler("listforward", handle_listforward))

    # 模式与控制
    app.add_handler(CommandHandler("setquiet", handle_setquiet))
    app.add_handler(CommandHandler("setvoting", handle_setvoting))
    app.add_handler(CommandHandler("preview", handle_preview))

    # 自动回复触发器 (Triggers)
    app.add_handler(CommandHandler("addtrigger", handle_addtrigger))
    app.add_handler(CommandHandler("deltrigger", handle_deltrigger))
    app.add_handler(CommandHandler("listtriggers", handle_listtriggers))

    # --- 信息查询 (Info) ---
    app.add_handler(CommandHandler("listchats", handle_listchats))
    app.add_handler(CommandHandler("chatinfo", handle_chatinfo))
    app.add_handler(CommandHandler("stats", handle_stats))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("queue", handle_queue_status))

    # =========================
    # 逻辑处理器 (Logic Handlers)
    # =========================

    # 1. 按钮回调 (投票功能)
    app.add_handler(CallbackQueryHandler(handle_vote_callback, pattern="^vote_"))

    # 2. 文本消息处理 (自动回复触发器)
    # 注意：需放在命令 Handler 之后，处理非命令文本
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # 3. 媒体消息处理 (核心功能：去重、清理、转发)
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))

    # =========================
    # 定时任务 (Job Queue)
    # =========================
    if app.job_queue:
        # 每天 UTC 04:00 (北京时间 12:00) 执行数据库清理
        app.job_queue.run_daily(daily_maintenance, time=time(4, 0, 0))
        print("⏰ 已设置每日 04:00 自动清理任务")

    print("🚀 Bot 已启动，正在运行中...")
    app.run_polling()


if __name__ == "__main__":
    main()