# main.py
# 启动 Telegram Bot，注册所有处理器，初始化数据库

from telegram.ext import ApplicationBuilder, MessageHandler, filters
from config import BOT_TOKEN
from db import init_db
from handlers.media import handle_media
from handlers.commands import (
    # 组合规则
    handle_setrules, handle_addrule, handle_delrule, handle_listrules, handle_clearrules,
    # 群组与信息
    handle_listchats, handle_chatinfo, handle_preview,
    # 关键词管理
    handle_addkw, handle_listkw, handle_delkw, handle_exportkw, handle_importkw,
    # 锁定/解锁
    handle_lock, handle_unlock,
    # 统计、帮助
    handle_stats, handle_help,
    # 管理员管理
    handle_addadmin, handle_deladmin, handle_listadmins,
    # 数据库备份恢复
    handle_backupdb, handle_restoredb
)

def main():
    if not BOT_TOKEN:
        print("❌ 请在 .env 文件中设置 BOT_TOKEN")
        return

    # 初始化数据库
    init_db()

    # 创建 Telegram 应用
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 注册群组/频道媒体清理处理器
    app.add_handler(MessageHandler(
        (filters.VIDEO | filters.PHOTO) & (filters.ChatType.GROUPS | filters.ChatType.CHANNEL),
        handle_media
    ))

    # 组合规则
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setrules "), handle_setrules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addrule "), handle_addrule))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delrule "), handle_delrule))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listrules "), handle_listrules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/clearrules "), handle_clearrules))

    # 群组与信息
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listchats"), handle_listchats))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/chatinfo "), handle_chatinfo))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/preview "), handle_preview))

    # 关键词管理
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addkw "), handle_addkw))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listkw "), handle_listkw))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delkw "), handle_delkw))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/exportkw "), handle_exportkw))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/importkw"), handle_importkw))

    # 锁定/解锁
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/lock "), handle_lock))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/unlock "), handle_unlock))

    # 管理员管理
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addadmin "), handle_addadmin))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/deladmin "), handle_deladmin))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listadmins"), handle_listadmins))

    # 数据库备份与恢复
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/backupdb"), handle_backupdb))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/restoredb"), handle_restoredb))

    # 统计与帮助
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/stats"), handle_stats))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/help"), handle_help))

    # 启动提示
    print("✅ Bot 已启动成功！")
    print("🔹 支持群组/频道媒体清理（组合规则）")
    print("🔸 支持私聊远程管理、关键词屏蔽、管理员管理、数据库备份恢复、统计分析")

    # 启动轮询监听
    app.run_polling()

# 程序入口
if __name__ == "__main__":
    main()