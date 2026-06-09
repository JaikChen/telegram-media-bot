8067701691:AAF42Qy-P3WrdEZxOUgbdukG25M5ZtMwr1gimport logging
import sys
from pathlib import Path

# Fix: Ensure project root is in sys.path for absolute 'src' imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, AIORateLimiter

from src.bot.core.config import BOT_TOKEN, VERSION, UPDATE_NOTES
from src.bot.core.logger import setup_logging
from src.bot.data.database import db_manager
from src.bot.data.repositories import MediaRepository
from src.bot.domain.forwarding import ForwardingService

# Import handlers
from src.bot.handlers.media import handle_media
from src.bot.handlers.chat_mgmt import (
    handle_setquiet,
    handle_setvoting,
    handle_setrules,
    handle_addrule,
    handle_delrule,
    handle_listrules,
    handle_clearrules,
    handle_addkw,
    handle_listkw,
    handle_delkw,
    handle_addreplace,
    handle_delreplace,
    handle_listreplace,
    handle_setfooter,
    handle_delfooter,
    handle_lock,
    handle_unlock,
    handle_preview,
    handle_addforward,
    handle_delforward,
    handle_listforward,
    handle_listallforwards,
    handle_allowuser,
    handle_blockuser,
    handle_listallowed,
    handle_addtrigger,
    handle_deltrigger,
    handle_listtriggers,
    handle_settemplate,
    handle_deltemplate,
    handle_setfilter,
)
from src.bot.handlers.sys_admin import (
    handle_addadmin,
    handle_deladmin,
    handle_listadmins,
    handle_backupdb,
    handle_restoredb,
    handle_setlog,
    handle_dellog,
    handle_setlogfilter,
    handle_cleanchats,
    handle_cleandb,
    handle_leave,
    handle_setdelay,
    handle_pause,
    handle_resume,
    handle_dlq,
    handle_retry_dlq,
    handle_clear_dlq,
    handle_repair_queue,
)
from src.bot.handlers.info import handle_listchats, handle_chatinfo, handle_stats, handle_queue_status, handle_help
from src.bot.handlers.message import handle_text_message
from src.bot.handlers.callback import handle_vote_callback
from src.bot.handlers.extras import handle_edit_caption, send_weekly_report

from src.bot.utils.helpers import log_event


async def post_init(application: Application):
    """System checks and background task initialization."""
    await db_manager.get_db()
    # Trigger DB migration logic if necessary

    if await MediaRepository.peek_queue():
        application.job_queue.run_once(ForwardingService.forward_worker, 2, name="forward_worker")

    # Register Weekly Report Job (Every Sunday at 12:00)
    from datetime import time

    application.job_queue.run_daily(send_weekly_report, time=time(12, 0, 0), days=(6,))

    logger.info(f"🚀 Bot v{VERSION} initialized with Global Deduplication and Self-Cleaning.")
    await log_event(application.bot, f"Bot started v{VERSION}\n{UPDATE_NOTES}", category="system")


async def post_shutdown(application: Application):
    """Graceful shutdown logic."""
    await db_manager.close()


def main():
    # Ensure critical configuration exists
    from src.bot.core.config import ensure_config
    ensure_config()
    
    # Re-import BOT_TOKEN after ensure_config might have updated it
    import src.bot.core.config as config
    token = config.BOT_TOKEN

    # Ensure necessary directories exist
    from src.bot.core.config import BASE_DIR

    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "backups").mkdir(parents=True, exist_ok=True)

    setup_logging()
    global logger
    logger = logging.getLogger(__name__)

    app = (
        Application.builder()
        .token(token)
        .rate_limiter(AIORateLimiter(overall_max_rate=30, overall_time_period=1))
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Core Media Handler
    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Document.ALL | filters.AUDIO, handle_media
        )
    )

    # Info Handlers
    app.add_handler(CommandHandler("listchats", handle_listchats))
    app.add_handler(CommandHandler("chatinfo", handle_chatinfo))
    app.add_handler(CommandHandler("stats", handle_stats))
    app.add_handler(CommandHandler("queue", handle_queue_status))
    app.add_handler(CommandHandler("queue_status", handle_queue_status))
    app.add_handler(CommandHandler("help", handle_help))

    # Chat Management Handlers
    app.add_handler(CommandHandler("setquiet", handle_setquiet))
    app.add_handler(CommandHandler("setvoting", handle_setvoting))
    app.add_handler(CommandHandler("setrules", handle_setrules))
    app.add_handler(CommandHandler("addrule", handle_addrule))
    app.add_handler(CommandHandler("delrule", handle_delrule))
    app.add_handler(CommandHandler("listrules", handle_listrules))
    app.add_handler(CommandHandler("clearrules", handle_clearrules))
    app.add_handler(CommandHandler("addkw", handle_addkw))
    app.add_handler(CommandHandler("listkw", handle_listkw))
    app.add_handler(CommandHandler("delkw", handle_delkw))
    app.add_handler(CommandHandler("addreplace", handle_addreplace))
    app.add_handler(CommandHandler("delreplace", handle_delreplace))
    app.add_handler(CommandHandler("listreplace", handle_listreplace))
    app.add_handler(CommandHandler("setfooter", handle_setfooter))
    app.add_handler(CommandHandler("delfooter", handle_delfooter))
    app.add_handler(CommandHandler("lock", handle_lock))
    app.add_handler(CommandHandler("unlock", handle_unlock))
    app.add_handler(CommandHandler("preview", handle_preview))
    app.add_handler(CommandHandler("addforward", handle_addforward))
    app.add_handler(CommandHandler("delforward", handle_delforward))
    app.add_handler(CommandHandler("listforward", handle_listforward))
    app.add_handler(CommandHandler("listallforwards", handle_listallforwards))
    app.add_handler(CommandHandler("listall", handle_listallforwards))
    app.add_handler(CommandHandler("allowuser", handle_allowuser))
    app.add_handler(CommandHandler("blockuser", handle_blockuser))
    app.add_handler(CommandHandler("listallowed", handle_listallowed))
    app.add_handler(CommandHandler("addtrigger", handle_addtrigger))
    app.add_handler(CommandHandler("deltrigger", handle_deltrigger))
    app.add_handler(CommandHandler("listtriggers", handle_listtriggers))
    app.add_handler(CommandHandler("settemplate", handle_settemplate))
    app.add_handler(CommandHandler("deltemplate", handle_deltemplate))
    app.add_handler(CommandHandler("setfilter", handle_setfilter))

    # System Admin Handlers
    app.add_handler(CommandHandler("addadmin", handle_addadmin))
    app.add_handler(CommandHandler("deladmin", handle_deladmin))
    app.add_handler(CommandHandler("listadmins", handle_listadmins))
    app.add_handler(CommandHandler("backupdb", handle_backupdb))
    app.add_handler(CommandHandler("restoredb", handle_restoredb))
    app.add_handler(CommandHandler("setlog", handle_setlog))
    app.add_handler(CommandHandler("dellog", handle_dellog))
    app.add_handler(CommandHandler("setlogfilter", handle_setlogfilter))
    app.add_handler(CommandHandler("cleanchats", handle_cleanchats))
    app.add_handler(CommandHandler("cleandb", handle_cleandb))
    app.add_handler(CommandHandler("leave", handle_leave))
    app.add_handler(CommandHandler("setdelay", handle_setdelay))
    app.add_handler(CommandHandler("pause", handle_pause))
    app.add_handler(CommandHandler("resume", handle_resume))
    app.add_handler(CommandHandler("dlq", handle_dlq))
    app.add_handler(CommandHandler("retry_dlq", handle_retry_dlq))
    app.add_handler(CommandHandler("clear_dlq", handle_clear_dlq))
    app.add_handler(CommandHandler("repair_queue", handle_repair_queue))

    # Interaction Handlers
    app.add_handler(CallbackQueryHandler(handle_vote_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Edit Sync Handler
    app.add_handler(
        MessageHandler(filters.UpdateType.EDITED_MESSAGE | filters.UpdateType.EDITED_CHANNEL_POST, handle_edit_caption)
    )

    logger.info("📡 Application starting...")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
