# locales.py
# 集中管理 Bot 的回复文案，方便修改和多语言扩展

MESSAGES = {
    # 错误提示
    "no_permission": "🚫 *无权操作*：你没有该群组的管理权限，或不在管理员白名单中。",
    "args_error": "❌ *参数错误*。请检查输入格式。",
    "no_data": "📭 当前没有记录。",
    "not_found": "❌ 未找到相关记录。",
    "db_error": "⚠️ 数据库操作失败。",
    # 通用成功
    "success": "✅ 操作成功。",
    "saved": "✅ 已保存。",
    "deleted": "🗑 已删除。",
    # 模块：群组管理
    "quiet_set": "✅ 频道 `{}` 模式已设为：`{}`",
    "quiet_usage": "❌ 用法：`/setquiet -100xxx [off/quiet/autodel]`",
    "vote_set": "✅ 频道 `{}` 投票功能：`{}`",
    "vote_usage": "❌ 用法：`/setvoting -100xxx [on/off]`",
    "rules_cleared": "🧹 频道 `{}` 的规则已清空。",
    "rule_added": "✅ 规则已添加。",
    "rule_deleted": "🗑 规则已移除。",
    "kw_added": "✅ 已向 `{}` 添加 {} 个关键词。",
    "kw_deleted": "🗑 关键词已移除。",
    "footer_set": "✅ 页脚已更新。",
    "footer_deleted": "🗑 页脚已移除。",
    "locked": "🔒 频道已锁定 (暂停处理)。",
    "unlocked": "🔓 频道已解锁 (恢复处理)。",
    "forward_added": "✅ 转发关系建立：`{}` -> `{}`",
    "forward_deleted": "🗑 转发关系解除。",
    "whitelist_added": "✅ 用户 `{}` 已加入白名单。",
    "whitelist_deleted": "🗑 用户 `{}` 已移出白名单。",
    "trigger_added": "✅ 触发器已添加：`{}`",
    "trigger_deleted": "🗑 触发器已删除：`{}`",
    # 模块：系统管理
    "admin_added": "✅ 已添加动态管理员：`{}`",
    "admin_deleted": "🗑 已移除管理员：`{}`",
    "backup_caption": "📦 数据库自动备份",
    "restore_success": "✅ 数据库已恢复，建议重启 Bot。",
    "log_set": "✅ 日志频道已设为：`{}`",
    "log_off": "📴 日志已关闭。",
    "maintenance_complete": "✅ 维护完成：清理 {} 条记录，数据库已压缩。",
    # 队列状态
    "queue_status_title": "📊 *当前转发队列积压情况*",
    "queue_row": "• `{}` ({}) → **{}** 条待发",
    "queue_empty": "🎉 *队列空闲*：当前没有待转发的消息。",
    # [新增] 暂停/恢复
    "queue_paused": "⏸ **转发队列已暂停**。\n积压的消息将保留在数据库中，直到恢复。",
    "queue_resumed": "▶️ **转发队列已恢复**。\nBot 将继续处理积压任务。",
}


def get_text(key: str, *args) -> str:
    """获取格式化后的文案"""
    msg = MESSAGES.get(key, f"Missing text: {key}")
    if args:
        return msg.format(*args)
    return msg
