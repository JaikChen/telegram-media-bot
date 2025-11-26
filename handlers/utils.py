# handlers/utils.py
# 权限检查辅助函数

from telegram.ext import ContextTypes
from config import ADMIN_IDS
from db import list_admins


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
    - 固定管理员：直接通过
    - 动态管理员：需检查是否为该频道的 Telegram 管理员/群主
    """
    uid = str(user_id)
    if is_global_admin(uid):
        return True

    # 动态管理员需验证 TG 权限
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception:
        # 无法获取成员信息（如 Bot 不在频道中），视为无权
        return False