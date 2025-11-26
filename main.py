# main.py
# 程序入口：初始化数据库，注册命令和消息处理器，启动 Bot

import logging
from telegram.ext import Application, MessageHandler, filters
from config import BOT_TOKEN
from db import init_db
from handlers.media import handle_media

# 导入新拆分的模块
from handlers.sys_admin import (
    handle_addadmin, handle_deladmin, handle_listadmins,
    handle_backupdb, handle_restoredb,
    handle_setlog, handle_dellog,
    handle_cleanchats, handle_leave
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
    handle_setquiet  # 静音/清理模式
)
from handlers.info import (
    handle_listchats, handle_chatinfo, handle_stats, handle_help
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

    # =========================
    # 注册命令处理器
    # =========================

    # --- 系统管理 (仅固定管理员) ---
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addadmin(\s|$)"), handle_addadmin))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/deladmin(\s|$)"), handle_deladmin))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listadmins(\s|$)"), handle_listadmins))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/backupdb(\s|$)"), handle_backupdb))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/restoredb(\s|$)"), handle_restoredb))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setlog(\s|$)"), handle_setlog))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/dellog(\s|$)"), handle_dellog))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/cleanchats(\s|$)"), handle_cleanchats))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/leave(\s|$)"), handle_leave))

    # --- 群组配置 ---
    # 规则
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setrules(\s|$)"), handle_setrules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addrule(\s|$)"), handle_addrule))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delrule(\s|$)"), handle_delrule))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listrules(\s|$)"), handle_listrules))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/clearrules(\s|$)"), handle_clearrules))
    # 关键词
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addkw(\s|$)"), handle_addkw))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listkw(\s|$)"), handle_listkw))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delkw(\s|$)"), handle_delkw))
    # 替换
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addreplace(\s|$)"), handle_addreplace))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delreplace(\s|$)"), handle_delreplace))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listreplace(\s|$)"), handle_listreplace))
    # 页脚
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setfooter(\s|$)"), handle_setfooter))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delfooter(\s|$)"), handle_delfooter))
    # 锁定
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/lock(\s|$)"), handle_lock))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/unlock(\s|$)"), handle_unlock))
    # 转发
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/addforward(\s|$)"), handle_addforward))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delforward(\s|$)"), handle_delforward))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listforward(\s|$)"), handle_listforward))
    # 白名单
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/allowuser(\s|$)"), handle_allowuser))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/blockuser(\s|$)"), handle_blockuser))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listallowed(\s|$)"), handle_listallowed))
    # 静音/清理模式
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/setquiet(\s|$)"), handle_setquiet))
    # 预览
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/preview(\s|$)"), handle_preview))

    # --- 信息查询 ---
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/listchats(\s|$)"), handle_listchats))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/chatinfo(\s|$)"), handle_chatinfo))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/stats(\s|$)"), handle_stats))
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