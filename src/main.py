import logging
import sys
from pathlib import Path

# Fix: Ensure project root is in sys.path for absolute 'src' imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, AIORateLimiter, ContextTypes

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
    handle_clear_queue,
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


class ProcessLock:
    """
    Robust single-instance process lock.
    On Windows: uses a shared-access file handle + msvcrt.locking on a pre-written byte.
    On Unix: uses fcntl exclusive lock.
    The key fix vs. the old implementation: we open with 'a' (append) mode so we
    never truncate the file, then check-and-lock, rather than truncating first.
    """
    def __init__(self, lock_path):
        self.lock_path = str(lock_path)
        self.fp = None

    def acquire(self) -> bool:
        import os
        try:
            if sys.platform == 'win32':
                import msvcrt
                # Open for read+write, create if missing – never truncate
                flags = os.O_RDWR | os.O_CREAT
                fd = os.open(self.lock_path, flags, 0o644)
                self.fp = os.fdopen(fd, 'r+')
                # Ensure the file has at least 1 byte so locking works
                self.fp.seek(0, 2)  # seek to end
                if self.fp.tell() == 0:
                    self.fp.write(' ')
                    self.fp.flush()
                self.fp.seek(0)
                try:
                    msvcrt.locking(self.fp.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    self.fp.close()
                    self.fp = None
                    return False
                # Overwrite with our PID
                self.fp.seek(0)
                self.fp.write(str(os.getpid()).ljust(20))
                self.fp.flush()
                return True
            else:
                import fcntl
                self.fp = open(self.lock_path, 'a+')
                try:
                    fcntl.flock(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError:
                    self.fp.close()
                    self.fp = None
                    return False
                self.fp.seek(0)
                self.fp.write(str(os.getpid()).ljust(20))
                self.fp.flush()
                return True
        except Exception as e:
            if self.fp:
                try:
                    self.fp.close()
                except Exception:
                    pass
                self.fp = None
            return False

    def release(self):
        if self.fp:
            try:
                if sys.platform == 'win32':
                    import msvcrt
                    self.fp.seek(0)
                    try:
                        msvcrt.locking(self.fp.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                self.fp.close()
            except Exception:
                pass
            finally:
                self.fp = None
                import os
                try:
                    if os.path.exists(self.lock_path):
                        os.remove(self.lock_path)
                except Exception:
                    pass


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

    # Process Lock to prevent duplicate instances
    lock = ProcessLock(BASE_DIR / "data/bot.lock")
    if not lock.acquire():
        print("Error: Another instance of the bot is already running. Exiting...")
        sys.exit(1)

    setup_logging()
    global logger
    logger = logging.getLogger(__name__)
    import os
    logger.info(f"Process lock acquired by PID {os.getpid()}.")

    from telegram.request import HTTPXRequest
    proxy_val = config.PROXY_URL if config.PROXY_URL else None
    request_cfg = HTTPXRequest(
        proxy=proxy_val,
        connect_timeout=15.0,
        read_timeout=15.0,
        write_timeout=15.0,
        pool_timeout=5.0,
        connection_pool_size=64,
    )
    get_updates_request_cfg = HTTPXRequest(
        proxy=proxy_val,
        connect_timeout=15.0,
        read_timeout=30.0,
        write_timeout=15.0,
        pool_timeout=5.0,
        connection_pool_size=64,
    )

    app = (
        Application.builder()
        .token(token)
        .request(request_cfg)
        .get_updates_request(get_updates_request_cfg)
        .concurrent_updates(True)
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
    app.add_handler(CommandHandler("start", handle_help))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("listchats", handle_listchats))
    app.add_handler(CommandHandler("chatinfo", handle_chatinfo))
    app.add_handler(CommandHandler("stats", handle_stats))
    app.add_handler(CommandHandler("queue", handle_queue_status))
    app.add_handler(CommandHandler("queue_status", handle_queue_status))

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
    app.add_handler(CommandHandler("retrydlq", handle_retry_dlq))
    app.add_handler(CommandHandler("clear_dlq", handle_clear_dlq))
    app.add_handler(CommandHandler("cleardlq", handle_clear_dlq))
    app.add_handler(CommandHandler("clear_queue", handle_clear_queue))
    app.add_handler(CommandHandler("clearqueue", handle_clear_queue))
    app.add_handler(CommandHandler("repair_queue", handle_repair_queue))
    app.add_handler(CommandHandler("repair", handle_repair_queue))

    # Interaction Handlers
    app.add_handler(CallbackQueryHandler(handle_vote_callback))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Edit Sync Handler
    app.add_handler(
        MessageHandler(filters.UpdateType.EDITED_MESSAGE | filters.UpdateType.EDITED_CHANNEL_POST, handle_edit_caption)
    )

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Exception while handling an update:", exc_info=context.error)

    app.add_error_handler(error_handler)

    logger.info("📡 Application starting...")
    app.run_polling(
        drop_pending_updates=True,
        poll_interval=0.0,
        timeout=10,
        bootstrap_retries=-1,
        allowed_updates=[
            "message", "edited_message",
            "channel_post", "edited_channel_post",
            "callback_query",
        ],
    )


if __name__ == "__main__":
    main()
