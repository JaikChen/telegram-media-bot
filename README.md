# 🤖 Telegram Media Bot (Async Ultimate Edition)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Performance](https://img.shields.io/badge/AsyncIO-Powered-orange)]()

一款 **全异步、高性能** 的 Telegram 群组/频道媒体管理机器人。
专为社群净化、媒体搬运、互动运营设计。集成了智能去重、广告拦截、自动转发、相册合并、互动投票等数十项功能，是群组管理的终极解决方案。

> 🚀 **新版特性**: 核心逻辑全面重构为 `AsyncIO` + `aiosqlite`，支持高并发处理，内置智能限流防封号，完美支持 Docker 一键部署。

---

## ✨ 核心亮点 (Key Features)

### ⚡️ **高性能架构**
* **全异步 I/O**: 采用 `aiosqlite` 数据库驱动，彻底告别阻塞，轻松应对高并发消息。
* **长连接池**: 数据库连接复用技术，查询速度大幅提升。
* **智能限流**: 内置 `AIORateLimiter`，自动处理 Telegram API 的速率限制，防止 `429` 错误。
* **相册防泄漏**: 使用 `TTLCache` 智能缓存相册组，自动回收内存，运行更稳定。

### 🛡️ **硬核内容净化**
* **智能去广告**: 支持 **温和模式**（仅删含广告行）和 **严格模式**（删整条消息）。
* **关键词增强**:
    * **批量添加**: 支持一次指令添加多个关键词。
    * **一键全群应用**: 超级管理员可使用 `all` 关键字将规则应用到所有频道。
    * **正则支持**: 原生支持 Regex 正则表达式屏蔽。
* **链接净化**: 智能识别并移除文本中的链接，甚至支持移除 Markdown 隐藏链接。
* **白名单机制**: 允许特定用户（如金主、管理员）豁免清理规则。

### 🚀 **媒体自动化**
* **智能去重**: 基于文件指纹 (`file_unique_id`)，自动删除重复发送的媒体。
* **自动转发**: 支持多对多转发映射，转发时自动应用清理规则、页脚和替换词。
* **完美相册**: 完美支持多图/视频相册 (Media Group)，自动去重并保留首条说明。
* **自动防剧透**: 发送带 `#spoiler` / `#剧透` / `#nsfw` 的媒体时，Bot 自动打码并重新发送。

### ⚙️ **企业级运维**
* **队列管理**: 支持 **查看积压**、**手动暂停/恢复** 转发任务，灵活应对突发流量。
* **日志中心**: 将清理、转发、错误日志推送到指定频道，支持按类型过滤。
* **自动维护**: 每日凌晨自动清理过期数据（保留 1 年）并压缩数据库 (VACUUM)。
* **数据库灾备**: 支持一键热备份 (`/backupdb`) 和热恢复 (`/restoredb`)。

---

## 🛠 快速部署 (Deployment)

### 方式一：Docker 部署 (推荐 ⭐️)

无需配置 Python 环境，最稳定、最干净的运行方式。

1.  **下载代码**
    ```bash
    git clone [https://github.com/your-repo/telegram-media-bot.git](https://github.com/your-repo/telegram-media-bot.git)
    cd telegram-media-bot
    ```

2.  **配置环境**
    创建 `.env` 文件并填入你的信息：
    ```bash
    touch .env
    ```
    **`.env` 文件内容示例**：
    ```ini
    # 你的 Bot Token (找 @BotFather 获取)
    BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
    
    # 超级管理员 ID (找 @userinfobot 获取)，多个 ID 用逗号分隔
    ADMIN_IDS=123456789,987654321
    ```

3.  **启动服务**
    ```bash
    docker-compose up -d
    ```

### 方式二：本地 Python 部署

适用于开发调试或无 Docker 环境。

1.  **环境要求**: Python 3.10+
2.  **安装依赖**:
    ```bash
    # 建议使用虚拟环境
    python -m venv .venv
    source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate
    
    # 强制安装兼容版本
    pip install -r requirements.txt --force-reinstall
    ```
3.  **启动**:
    ```bash
    python main.py
    ```

---

## 📖 详细命令手册 (User Guide)

> **💡 提示**: 
> 1. 所有命令仅限 **管理员 (Admin)** 使用。
> 2. `{target}` 参数：在群内直接发送指令时无需填写；私聊 Bot 操作时需填入 `-100xxxx` 形式的频道 ID。
> 3. 🔥 **超级管理员**可将 `{target}` 填为 `all`，以对**所有频道**执行批量操作（支持规则、关键词等）。

### 1. 🧩 规则与内容控制 (Chat Management)

| 指令 | 描述 | 示例 |
| :--- | :--- | :--- |
| `/setrules {target} 规则...` | **覆盖设置**所有规则 (逗号分隔) | `/setrules all clean_links` |
| `/addrule {target} 规则` | **添加**单条规则 | `/addrule all remove_at_prefix` |
| `/delrule {target} 规则` | **删除**单条规则 | `/delrule -100xxx block_keywords` |
| `/listrules {target}` | 查看当前规则列表 | |
| `/clearrules {target}` | 清空所有规则 | |

**📝 可用规则参数详解**:
* `keep_all`: **保留所有**，不做任何删除（仅转发/加页脚）。
* `clean_keywords`: **温和屏蔽**。若某行含屏蔽词，仅删除该行。
* `block_keywords`: **严格屏蔽**。若含屏蔽词，删除整条消息说明。
* `strip_all_if_links`: **严格删链**。若含链接，删除整条消息说明。
* `clean_links`: **温和删链**。仅剔除链接文本，保留其他文字。
* `remove_at_prefix`: 删除所有 `@username` 引用。
* `maxlen:50`: 限制长度不超过 50 字，超长则清空。

### 2. 🛠 关键词与增强 (Enhancement)

* **关键词管理**:
    * `/addkw {target} 词1 词2 ... [regex]`：批量添加屏蔽词（支持正则）。
    * `/delkw {target} 词`：删除屏蔽词。
    * `/listkw {target}`：查看列表。
* **文本替换**:
    * `/addreplace {target} 旧词 新词`：自动将文案中的 A 变为 B。
    * `/listreplace {target}`：查看替换表。
* **小尾巴 (Footer)**:
    * `/setfooter {target} 内容`：在清理后的文字末尾追加推广信息。
    * `/delfooter {target}`：删除页脚。

### 3. 🎮 交互与自动回复 (Interaction)

* **Bot 模式设置**:
    * `/setquiet {target} off`：**正常模式** (默认)。
    * `/setquiet {target} autodel`：**阅后即焚** (推荐)，Bot 的操作提示 10秒后自动消失。
* **互动投票**:
    * `/setvoting {target} on/off`：发送图片/视频时自动附加 👍👎 按钮。
* **关键词自动回复 (FAQ)**:
    * `/addtrigger {target} 关键词 回复内容`：用户触发关键词时自动回复。
    * `/listtriggers {target}`：查看触发器列表。

### 4. 🔁 转发系统 (Forwarding)

建立频道间的自动搬运管道，支持 **相册合并转发**。

* `/addforward -100源ID -100目标ID`：建立转发关系。
* `/delforward -100源ID -100目标ID`：解除关系。
* `/listforward -100源ID`：查看转发链。
* `/queue`：📊 **查看当前转发积压状态**。

### 5. ⚙️ 系统管理 (Super Admin)

> ⚠️ 仅限 `.env` 中配置的 `ADMIN_IDS` 用户使用。

* **转发控制**:
    * `/pause`：⏸ **暂停转发**（积压消息保留在数据库）。
    * `/resume`：▶️ **恢复转发**（继续处理积压）。
    * `/setdelay min max`：设置随机延迟转发时间（秒）。
* **日志系统**:
    * `/setlog -100日志频道ID`：设置日志输出频道。
    * `/setlogfilter clean error`：过滤日志类型。
* **维护工具**:
    * `/cleanchats`：一键清理数据库中无效/被踢出的群组数据。
    * `/cleandb`：手动触发数据库压缩与过期清理。
    * `/backupdb` & `/restoredb`：数据库备份与恢复。
* **管理员管理**:
    * `/addadmin 用户ID`：添加动态管理员（无需重启 Bot）。
    * `/listadmins`：查看所有管理员。

---

## 📂 项目结构

```text
telegram-media-bot/
├── main.py               # [入口] 程序启动、调度器、路由注册
├── db.py                 # [核心] 异步数据库封装 (aiosqlite)
├── cleaner.py            # [核心] 文本清洗算法 (正则/标签回填)
├── config.py             # [配置] 环境配置加载
├── locales.py            # [文案] 集中式提示语管理
├── requirements.txt      # [依赖] 项目依赖包
├── Dockerfile            # [部署] Docker 构建文件
└── handlers/             # [模块] 功能逻辑拆分
    ├── media.py          # 媒体处理 (去重/转发/相册)
    ├── chat_mgmt.py      # 群组管理指令
    ├── sys_admin.py      # 系统级指令
    ├── info.py           # 信息与队列查询
    ├── utils.py          # 通用工具 & 鉴权装饰器
    └── ...
```
📄 License

MIT License.