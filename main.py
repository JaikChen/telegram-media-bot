# main.py
# 程序入口：初始化数据库，注册命令和消息处理器，启动 Bot

import logging
from telegram.ext import Application, MessageHandler, filters
from config import BOT_TOKEN
from db import init_db
from handlers.media import handle_media
from handlers.commands import (
    # 规则管理
    handle_setrules, handle_addrule, handle_delrule, handle_listrules, handle_clearrules,
    # 群组管理
    handle_listchats, handle_chatinfo, handle_cleanchats, handle_leave,
    # 预览
    handle_preview,
    # 关键词管理
    handle_addkw, handle_listkw, handle_delkw,
    # 替换词管理
    handle_addreplace, handle_delreplace, handle_listreplace,
    # 页脚管理
    handle_setfooter, handle_delfooter,
    # 锁定管理
    handle_lock, handle_unlock,
    # 统计
    handle_stats,
    # 管理员管理
    handle_addadmin, handle_deladmin, handle_listadmins,
    # 转发管理
    handle_addforward, handle_delforward, handle_listforward,
    # 数据库管理
    handle_backupdb, handle_restoredb,
    # 日志管理
    handle_setlog, handle_dellog,
    # 帮助
    handle_help
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


def main():
    # 初始化数据库
    init_db()

    # 创建应用 (不使用 post_init 设置指令)
    app = Application.builder().token(BOT_TOKEN).build()

    # =========================
    # 注册命令处理器
    # =========================

    # 1. 组合规则管理
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setrules(\s|$)"), handle_setrules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addrule(\s|$)"), handle_addrule))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delrule(\s|$)"), handle_delrule))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listrules(\s|$)"), handle_listrules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/clearrules(\s|$)"), handle_clearrules))

    # 2. 群组管理
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listchats(\s|$)"), handle_listchats))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/chatinfo(\s|$)"), handle_chatinfo))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/cleanchats(\s|$)"), handle_cleanchats))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/leave(\s|$)"), handle_leave))

    # 3. 预览功能
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/preview(\s|$)"), handle_preview))

    # 4. 关键词管理
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addkw(\s|$)"), handle_addkw))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listkw(\s|$)"), handle_listkw))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delkw(\s|$)"), handle_delkw))

    # 5. 替换词管理
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addreplace(\s|$)"), handle_addreplace))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delreplace(\s|$)"), handle_delreplace))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listreplace(\s|$)"), handle_listreplace))

    # 6. 页脚管理
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setfooter(\s|$)"), handle_setfooter))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delfooter(\s|$)"), handle_delfooter))

    # 7. 锁定与统计
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/lock(\s|$)"), handle_lock))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/unlock(\s|$)"), handle_unlock))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/stats(\s|$)"), handle_stats))

    # 8. 管理员管理
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addadmin(\s|$)"), handle_addadmin))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/deladmin(\s|$)"), handle_deladmin))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listadmins(\s|$)"), handle_listadmins))

    # 9. 转发映射管理
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addforward(\s|$)"), handle_addforward))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delforward(\s|$)"), handle_delforward))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listforward(\s|$)"), handle_listforward))

    # 10. 数据库备份与恢复
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/backupdb(\s|$)"), handle_backupdb))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/restoredb(\s|$)"), handle_restoredb))

    # 11. 日志管理
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setlog(\s|$)"), handle_setlog))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/dellog(\s|$)"), handle_dellog))

    # 12. 帮助命令
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/help(\s|$)"), handle_help))

    # =========================
    # 注册媒体消息处理器
    # =========================
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))

    # 启动 Bot
    print("🚀 Bot 已启动...")
    app.run_polling()


if __name__ == "__main__":
    main()