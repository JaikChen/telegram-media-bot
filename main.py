# main.py
import logging
from datetime import time
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, filters
from config import BOT_TOKEN
from db import init_db, clean_expired_data, vacuum_db
from handlers.media import handle_media

from handlers.sys_admin import (
    handle_addadmin, handle_deladmin, handle_listadmins,
    handle_backupdb, handle_restoredb,
    handle_setlog, handle_dellog, handle_setlogfilter,
    handle_cleanchats, handle_cleandb, handle_leave
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
    handle_listchats, handle_chatinfo, handle_stats, handle_help
)
from handlers.callback import handle_vote_callback
from handlers.message import handle_text_message

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def daily_maintenance(context):
    print("⏳ 每日维护...")
    deleted = clean_expired_data(days=365)
    vacuum_db()
    print(f"✅ 完成，清理 {deleted} 条")


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # 系统
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addadmin"), handle_addadmin))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/deladmin"), handle_deladmin))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listadmins"), handle_listadmins))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/backupdb"), handle_backupdb))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/restoredb"), handle_restoredb))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setlog(\s|$)"), handle_setlog))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/dellog"), handle_dellog))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setlogfilter"), handle_setlogfilter))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/cleanchats"), handle_cleanchats))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/cleandb"), handle_cleandb))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/leave"), handle_leave))

    # 群管
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setrules"), handle_setrules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addrule"), handle_addrule))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delrule"), handle_delrule))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listrules"), handle_listrules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/clearrules"), handle_clearrules))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addkw"), handle_addkw))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listkw"), handle_listkw))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delkw"), handle_delkw))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addreplace"), handle_addreplace))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delreplace"), handle_delreplace))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listreplace"), handle_listreplace))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setfooter"), handle_setfooter))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delfooter"), handle_delfooter))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/lock"), handle_lock))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/unlock"), handle_unlock))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addforward"), handle_addforward))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delforward"), handle_delforward))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listforward"), handle_listforward))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/allowuser"), handle_allowuser))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/blockuser"), handle_blockuser))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listallowed"), handle_listallowed))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setquiet"), handle_setquiet))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setvoting"), handle_setvoting))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addtrigger"), handle_addtrigger))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/deltrigger"), handle_deltrigger))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listtriggers"), handle_listtriggers))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/preview"), handle_preview))

    # 信息
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listchats"), handle_listchats))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/chatinfo"), handle_chatinfo))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/stats"), handle_stats))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/help"), handle_help))

    # 逻辑处理
    app.add_handler(CallbackQueryHandler(handle_vote_callback, pattern="^vote_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))

    if app.job_queue:
        app.job_queue.run_daily(daily_maintenance, time=time(4, 0, 0))
        print("⏰ 已设置每日 04:00 自动清理任务")

    print("🚀 Bot 已启动...")
    app.run_polling()


if __name__ == "__main__":
    main()