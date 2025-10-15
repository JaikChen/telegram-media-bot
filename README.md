# Telegram Media Cleaner Bot

一个基于 Python 的 Telegram Bot，用于自动清理群组/频道媒体说明文字（caption），支持灵活的组合规则、关键词屏蔽、管理员远程管理、数据库备份恢复等功能。

---

## ✨ 功能特性

- **媒体说明清理**
  - 自动清理群组/频道中图片、视频的说明文字
  - 支持多种规则组合：  
    - `clean_links` → 删除链接  
    - `strip_all_if_links` → 有链接就整段删除  
    - `remove_at_prefix` → 删除 @前缀  
    - `block_keywords` → 屏蔽关键词（支持正则）  
    - `keep_all` → 保留所有说明  
    - `maxlen:NN` → 限制说明最大长度（超过则清理）

- **关键词管理**
  - 添加/删除/列出关键词
  - 支持正则关键词
  - 批量导入/导出关键词（文本或文件）

- **管理员管理**
  - 固定管理员（写在 `config.py`）
  - 动态管理员（通过命令添加/删除）
  - 查看管理员列表

- **频道管理**
  - 列出 Bot 所在频道/群组
  - 查看频道信息（名称 + 规则）

- **锁定/解锁**
  - 可暂停/恢复某个频道的清理功能

- **统计**
  - 统计各频道清理次数

- **数据库管理**
  - 备份数据库文件
  - 恢复数据库（上传文件）

---

## 🚀 安装与运行

### 1. 克隆项目
```bash
git clone https://github.com/yourname/telegram-media-bot.git
cd telegram-media-bot
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
在项目根目录创建 `.env` 文件：
```env
BOT_TOKEN=你的TelegramBotToken
```

在 `config.py` 中设置固定管理员 ID：
```python
ADMIN_IDS = {
    "123456789",  # 你的 Telegram 用户ID
}
```

### 4. 运行
```bash
python main.py
```

---

## 📖 管理命令

所有命令仅限管理员私聊使用。

### 🔧 组合规则
```text
/setrules -100频道ID 规则1,规则2,...
  示例：/setrules -100123 clean_links,remove_at_prefix,block_keywords,maxlen:80

/addrule -100频道ID 规则
  示例：/addrule -100123 maxlen:100

/delrule -100频道ID 规则
  示例：/delrule -100123 strip_all_if_links

/listrules -100频道ID
  示例：/listrules -100123

/clearrules -100频道ID
  示例：/clearrules -100123
```

### 👥 群组管理
```text
/listchats
/chatinfo -100频道ID
```

### 🧹 说明预览
```text
/preview -100频道ID 说明文字
  示例：/preview -100123 这是一个测试说明
```

### 📝 关键词管理
```text
/addkw -100频道ID 关键词 [regex]
  示例：/addkw -100123 广告
  示例：/addkw -100123 \d{11} regex

/listkw -100频道ID
/delkw -100频道ID 关键词
/exportkw -100频道ID
/importkw -100频道ID 关键词1,关键词2,...
  或 回复关键词文件并输入 /importkw -100频道ID
```

### 🔒 锁定/解锁
```text
/lock -100频道ID
/unlock -100频道ID
```

### 📊 统计
```text
/stats
```

### 👑 管理员管理
```text
/addadmin 用户ID
/deladmin 用户ID
/listadmins
```

### 💾 数据库
```text
/backupdb
/restoredb （需回复数据库文件）
```

---

## 📦 数据库结构

- `seen`：已处理过的媒体（去重）
- `chats`：频道/群组信息
- `rules`：频道规则
- `keywords`：关键词
- `locked`：锁定状态
- `stats`：清理统计
- `admins`：动态管理员

---

## 🛠 开发说明

- Python 版本：3.9+
- 依赖库：`python-telegram-bot` v20+
- 数据库：SQLite

---

