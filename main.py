# main.py
import logging
from datetime import time
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, filters, AIORateLimiter
from config import BOT_TOKEN
from db import init_db, clean_expired_data, vacuum_db, init_db_connection, close_db_connection

from handlers.media import handle_media
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
    handle_allowuser, handle_blockuser, handle_listallowed,
    handle_setquiet, handle_setvoting,
    handle_addforward, handle_delforward, handle_listforward,
    handle_lock, handle_unlock,
    handle_addtrigger, handle_deltrigger, handle_listtriggers
)

from handlers.info import (
    handle_listchats, handle_chatinfo, handle_stats, handle_help
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)


async def daily_maintenance(context):
    print("⏳ [System] 执行每日维护任务...")
    deleted = await clean_expired_data(days=365)
    await vacuum_db()
    print(f"✅ [System] 维护完成，清理了 {deleted} 条过期记录。")


async def post_init(application):
    """启动前初始化"""
    print("⏳ [System] 正在初始化数据库连接...")
    await init_db_connection()
    await init_db()
    print("✅ [System] 数据库就绪。")


async def post_shutdown(application):
    """关闭时清理"""
    print("🔌 [System] 正在关闭数据库连接...")
    await close_db_connection()


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .rate_limiter(AIORateLimiter(overall_max_rate=30, overall_time_period=1))
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # 系统管理
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/addadmin"), handle_addadmin))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/deladmin"), handle_deladmin))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/listadmins"), handle_listadmins))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/backupdb"), handle_backupdb))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/restoredb"), handle_restoredb))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/setlogfilter"), handle_setlogfilter))  # 先匹配长命令
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/setlog"), handle_setlog))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/dellog"), handle_dellog))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/cleanchats"), handle_cleanchats))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/cleandb"), handle_cleandb))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/leave"), handle_leave))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/setdelay"), handle_setdelay))

    # 群组管理
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/setrules"), handle_setrules))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/addrule"), handle_addrule))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/delrule"), handle_delrule))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/listrules"), handle_listrules))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/clearrules"), handle_clearrules))

    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/addkw"), handle_addkw))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/listkw"), handle_listkw))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/delkw"), handle_delkw))

    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/addreplace"), handle_addreplace))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/delreplace"), handle_delreplace))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/listreplace"), handle_listreplace))

    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/setfooter"), handle_setfooter))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/delfooter"), handle_delfooter))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/allowuser"), handle_allowuser))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/blockuser"), handle_blockuser))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/listallowed"), handle_listallowed))

    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/lock"), handle_lock))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/unlock"), handle_unlock))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/addforward"), handle_addforward))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/delforward"), handle_delforward))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/listforward"), handle_listforward))

    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/setquiet"), handle_setquiet))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/setvoting"), handle_setvoting))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/preview"), handle_preview))

    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/addtrigger"), handle_addtrigger))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/deltrigger"), handle_deltrigger))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/listtriggers"), handle_listtriggers))

    # 信息查询
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/listchats"), handle_listchats))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/chatinfo"), handle_chatinfo))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/stats"), handle_stats))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/help"), handle_help))

    # 逻辑处理
    app.add_handler(CallbackQueryHandler(handle_vote_callback, pattern="^vote_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))

    if app.job_queue:
        app.job_queue.run_daily(daily_maintenance, time=time(4, 0, 0))

    print("🚀 Bot 已启动...")
    app.run_polling()


if __name__ == "__main__":
    main()