# 🤖 Telegram Media Bot (Ultimate Edition)

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://www.python.org/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-blue?logo=telegram)](https://core.telegram.org/bots/api)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

一款 **全能型** Telegram 群组/频道管理机器人。
专为社群净化、媒体搬运、互动运营而设计。集成了智能去重、广告拦截、自动转发、互动投票、关键词回复等数十项功能，是群组管理的终极解决方案。

---

## ✨ 核心特性 (Features)

### 🛡️ **硬核内容净化**
* **智能去广告**：支持 **温和模式**（仅删除含广告的行）和 **严格模式**（删除整条消息）。
* **关键词增强**：
    * **一键全群添加**：超级管理员可一键对所有已记录群组添加屏蔽词。
    * **批量添加**：支持一次指令添加多个关键词。
    * **正则支持**：原生支持 Regex 正则表达式屏蔽。
* **链接净化**：智能识别并移除文本中的链接，甚至支持移除 Markdown 隐藏链接。
* **白名单机制**：允许特定用户（如赞助者）豁免清理规则。

### 🚀 **媒体自动化**
* **智能去重**：
    * 基于媒体文件指纹 (`file_unique_id`)。
    * **滚动清理机制**：自动保留最近 **1 年** 的记录，过期数据每日自动清理。
* **自动转发**：支持多对多转发映射，转发时自动应用清理规则、页脚和替换词。
* **相册支持**：完美支持多图/视频相册 (Media Group)，自动去重并保留首条说明。
* **自动防剧透**：发送带 `#spoiler` / `#剧透` / `#nsfw` 的媒体时，Bot 自动打码并重新发送。

### 🎮 **社群运营与互动**
* **互动投票**：转发/发送单张图片视频时，自动附加 👍 / 👎 按钮，实时统计热度。
* **自动回复 (FAQ)**：自定义关键词触发器，自动回答常见问题或接梗。
* **静音/阅后即焚**：支持 `quiet`（完全静音）和 `autodel`（操作提示 10秒后自毁）模式，拒绝 Bot 刷屏。

### ⚙️ **企业级运维**
* **日志中心**：将清理、转发、错误日志推送到指定频道，支持按类型过滤（如只看错误日志）。
* **数据库维护**：支持一键备份、恢复，每日凌晨自动 VACUUM 整理碎片。
* **权限隔离**：Super Admin (全系统) 与 Chat Admin (仅当前群) 权限分离。

---

## 🛠 环境与部署

* **系统**: Linux (Ubuntu/Debian/CentOS)
* **Python**: 3.11+
* **数据库**: SQLite (自动生成，零配置)

### ⚡️ 一键部署

1.  **下载代码**
    ```bash
    git clone [https://github.com/your-repo/telegram-media-bot.git](https://github.com/your-repo/telegram-media-bot.git)
    cd telegram-media-bot
    ```

2.  **配置环境**
    创建 `.env` 文件：
    ```bash
    echo "BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11" > .env
    echo "ADMIN_IDS=123456789,987654321" >> .env
    ```

3.  **运行安装脚本**
    ```bash
    chmod +x deploy_bot.sh
    sudo ./deploy_bot.sh
    ```

4.  **查看日志**
    ```bash
    sudo journalctl -u telegram-media-bot -f
    ```

---

## 📖 详细使用指南

> **说明**：
> * `{target}` 代表目标，在群内直接发送无需参数，私聊时请填 `-100频道ID`。
> * 只有管理员可以使用以下命令。

### 1. 🧩 规则与配置 (Rules)

控制 Bot 如何处理每一条媒体消息的说明文字。

| 指令 | 描述 |
| :--- | :--- |
| `/setrules {target} 规则...` | **覆盖设置**所有规则 (逗号分隔) |
| `/addrule {target} 规则` | **添加**单条规则 |
| `/delrule {target} 规则` | **删除**单条规则 |
| `/listrules {target}` | 查看当前规则列表 |
| `/clearrules {target}` | 清空所有规则 |

#### 📝 可用规则参数详解

| 规则代码 | 作用 | 适用场景 |
| :--- | :--- | :--- |
| `keep_all` | **保留所有**，不做任何删除。 | 仅需转发或添加页脚时使用。 |
| `clean_keywords` | **温和屏蔽**。若某行包含屏蔽词，**仅删除该行**，保留其他文字。 | 适用于去除文案中的“广告行”。 |
| `block_keywords` | **严格屏蔽**。若含屏蔽词，**删除整段**说明文字。 | 适用于零容忍广告。 |
| `strip_all_if_links` | **严格删链**。若含链接，**删除整段**说明文字。 | 防止任何外链引流。 |
| `clean_links` | **温和删链**。仅剔除链接文本，保留其他文字。 | 保留文案但移除链接。 |
| `remove_at_prefix` | 删除所有 `@username` 引用。 | 去除来源标记。 |
| `maxlen:50` | 限制长度不超过 50 字，超长则清空。 | 保持版面整洁。 |

---

### 2. 🛠 内容增强 (Enhancement)

让 Bot 自动优化内容格式。

#### 🔑 关键词管理
* `/addkw {target} 词1 词2 ... [regex]`：批量添加屏蔽词。
* `/addkw all 词1 词2 ...`：**全群添加**（仅限超级管理员）。
* `/delkw {target} 词`：删除屏蔽词。
* `/listkw {target}`：查看列表。

#### 🔄 文本替换
将文案中的 A 自动变为 B（例如将搬运来源替换为自己的频道名）。
* `/addreplace {target} 旧词 新词`
* `/listreplace {target}`

#### 📝 自定义页脚
在清理后的文字末尾，自动追加一段推广信息。
* `/setfooter {target} 📢 关注频道 @MyChannel`
* `/delfooter {target}`

#### 🛡 用户白名单
允许特定用户（如赞助者）发送任意内容而不被清理。
* `/allowuser {target} 用户ID`
* `/listallowed {target}`

---

### 3. 🎮 控制与模式 (Control)

优化 Bot 的交互行为，避免打扰用户。

#### 🔕 静音模式
设置 Bot 回复命令的策略。
* `/setquiet {target} off`：**正常模式**（默认），有问必答。
* `/setquiet {target} quiet`：**静音模式**，成功时不说话，只报错。
* `/setquiet {target} autodel`：**阅后即焚**，Bot 的回复在 10秒后自动删除。**(推荐)**

#### 👍 互动投票
开关媒体消息下方的点赞按钮。
* `/setvoting {target} on`：开启投票（仅限单张图片/视频）。
* `/setvoting {target} off`：关闭投票。

#### 🤖 自动回复 (Triggers)
设置关键词自动应答（如 FAQ）。
* `/addtrigger {target} 价格 本群免费`：用户发“价格”时自动回复。
* `/listtriggers {target}`：查看触发器。

#### 🔒 锁定频道
* `/lock {target}`：暂停 Bot 对该频道的处理。
* `/unlock {target}`：恢复工作。

#### 🌫 自动防剧透
无需配置。发送媒体时在说明中带上 **`#spoiler`**、**`#剧透`** 或 **`#nsfw`**，Bot 会自动：
1.  删除原消息。
2.  以 **模糊遮罩 (Spoiler)** 形式重发媒体。
3.  保留原说明文字（可选去标签）。

---

### 4. 🔁 自动转发 (Forwarding)

建立频道间的自动搬运管道。

* `/addforward -100源ID -100目标ID`：建立转发关系。
* `/delforward -100源ID -100目标ID`：解除关系。
* `/listforward -100源ID`：查看该源频道的转发目标。

---

### 5. ⚙️ 系统管理 (Super Admin)

> ⚠️ **仅限配置文件中的 ADMIN_IDS 使用**

#### 📝 日志系统
* `/setlog -100日志频道ID`：设置日志输出频道。
* `/setlogfilter clean error system`：**过滤日志**。
    * 可选类型：`clean` (清理), `duplicate` (去重), `forward` (转发), `error` (错误), `system` (系统)。
* `/dellog`：关闭日志。

#### 🧹 维护工具
* `/cleanchats`：自动检测并清理数据库中 **无效/被踢出** 的群组数据。
* `/cleandb`：手动触发数据库维护（清理 1 年前的过期去重记录 + VACUUM）。
* `/leave -100xxx`：强制 Bot 退出指定群组。

#### 👥 管理员与备份
* `/addadmin 123456` / `/deladmin`：管理动态管理员。
* `/backupdb`：下载 `bot.db` 数据库文件。
* `/restoredb`：回复此命令并附带数据库文件以恢复数据。

---

## 📊 数据库自动维护机制

Bot 内置了无需人工干预的维护策略：

1.  **TTL 滚动清理**：
    * 每天 **UTC 04:00** 自动运行。
    * 自动删除 **365 天** 以前的媒体去重指纹。
    * *效果：允许老图在一年后重发，同时防止数据库无限增大。*
2.  **自动 VACUUM**：
    * 清理碎片，压缩数据库体积，保持查询速度。

---

## 📁 项目文件结构

```plaintext
telegram-media-bot/
├── main.py               # [入口] 程序启动、调度器、Handler注册
├── db.py                 # [核心] 数据库操作、缓存(LRU)、自动维护逻辑
├── cleaner.py            # [核心] 文本清理算法 (正则、实体检测、标签回填)
├── config.py             # [配置] 环境变量读取
├── handlers/             # [模块] 功能逻辑拆分
│   ├── media.py          # 媒体处理 (去重、转发、防剧透、相册)
│   ├── chat_mgmt.py      # 群组管理 (规则、关键词、静音、投票)
│   ├── sys_admin.py      # 系统管理 (数据库、日志、清理)
│   ├── info.py           # 信息查询 (帮助、统计、列表)
│   ├── callback.py       # 交互回调 (投票按钮响应)
│   ├── message.py        # 文本消息 (自动回复触发器)
│   └── utils.py          # 工具函数 (权限检查、日志发送、Markdown转义)
└── deploy_bot.sh         # 部署脚本