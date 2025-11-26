# handlers/utils.py
# 权限检查与消息回复辅助

from telegram.ext import ContextTypes
from config import ADMIN_IDS
from db import list_admins, get_quiet_mode


def is_global_admin(user_id: str | int) -> bool:
    """检查是否为固定配置的超级管理员"""
    return str(user_id) in ADMIN_IDS


async def is_admin(msg):
    """
    检查是否有权使用 Bot（基础门槛）。
    包含固定管理员和数据库中的动态管理员。
    """
    uid = str(msg.from_user.id)
    if is_global_admin(uid):
        return True
    return uid in list_admins()


async def check_chat_permission(user_id: int | str, chat_id: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    检查用户是否有权限管理指定频道。
    """
    uid = str(user_id)
    if is_global_admin(uid):
        return True

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception:
        return False


# [新增] 消息自动删除任务
async def delete_msg_job(context: ContextTypes.DEFAULT_TYPE):
    """用于 JobQueue 的删消息任务"""
    try:
        await context.job.data.delete()
    except Exception:
        pass


# [新增] 智能回复函数
async def reply_success(msg, context: ContextTypes.DEFAULT_TYPE, text: str, chat_id: str = None):
    """
    发送操作成功的消息，根据群组的静音设置进行处理：
    - off: 正常发送
    - quiet: 不发送
    - autodel: 发送后10秒自动删除
    """
    target_chat_id = chat_id if chat_id else str(msg.chat_id)

    # 获取该频道的设置，如果命令是针对频道的（如 /setrules -100xxx），应检查该频道的设置
    # 但通常命令是在私聊发的，回复也是发给私聊管理员。
    # 这里的逻辑是：如果管理员不想看刷屏，他可以在私聊里操作。
    # *修正*：这通常用于 Bot 在群里操作后的反馈，或者管理员操作后的反馈。
    # 既然命令大部分是私聊 Bot 使用的，我们暂时只检查传入的 chat_id (目标频道) 的配置。

    # 如果没有传入 chat_id，说明可能是通用命令，或者我们在私聊里回复，这里默认使用默认回复
    # 只有当命令明确操作某个频道时（如 /lock -100xxx），我们才应用该频道的静音策略

    if not chat_id:
        # 如果不知道是针对哪个频道的，就默认发送
        await msg.reply_text(text, parse_mode="Markdown")
        return

    mode = get_quiet_mode(chat_id)

    if mode == "quiet":
        # 静音模式：不发送成功消息
        return

    # 发送消息
    sent_msg = await msg.reply_text(text, parse_mode="Markdown")

    if mode == "autodel":
        # 阅后即焚：10秒后删除
        if context.job_queue:
            context.job_queue.run_once(delete_msg_job, 10, data=sent_msg)