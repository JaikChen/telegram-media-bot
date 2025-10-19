# main.py
# 程序入口：初始化数据库，注册命令和消息处理器，启动 Bot

import logging
from telegram.ext import Application, MessageHandler, filters
from config import BOT_TOKEN
from db import init_db
from handlers.media import handle_media
from handlers.commands import (
    handle_setrules, handle_addrule, handle_delrule, handle_listrules, handle_clearrules,
    handle_listchats, handle_chatinfo, handle_preview,
    handle_addkw, handle_listkw, handle_delkw,
    handle_lock, handle_unlock,
    handle_stats,
    handle_addadmin, handle_deladmin, handle_listadmins,
    handle_addforward, handle_delforward, handle_listforward,
    handle_backupdb, handle_restoredb,
    handle_help
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def main():
    # 初始化数据库
    init_db()

    # 创建应用
    app = Application.builder().token(BOT_TOKEN).build()

    # 注册命令处理器
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setrules(\s|$)"), handle_setrules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addrule(\s|$)"), handle_addrule))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delrule(\s|$)"), handle_delrule))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listrules(\s|$)"), handle_listrules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/clearrules(\s|$)"), handle_clearrules))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listchats(\s|$)"), handle_listchats))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/chatinfo(\s|$)"), handle_chatinfo))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/preview(\s|$)"), handle_preview))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addkw(\s|$)"), handle_addkw))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listkw(\s|$)"), handle_listkw))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delkw(\s|$)"), handle_delkw))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/lock(\s|$)"), handle_lock))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/unlock(\s|$)"), handle_unlock))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/stats(\s|$)"), handle_stats))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addadmin(\s|$)"), handle_addadmin))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/deladmin(\s|$)"), handle_deladmin))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listadmins(\s|$)"), handle_listadmins))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addforward(\s|$)"), handle_addforward))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delforward(\s|$)"), handle_delforward))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listforward(\s|$)"), handle_listforward))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/backupdb(\s|$)"), handle_backupdb))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/restoredb(\s|$)"), handle_restoredb))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/help(\s|$)"), handle_help))

    # 注册媒体处理器（照片、视频、相册）
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))

    # 启动 Bot
    app.run_polling()

if __name__ == "__main__":
    main()