# 🤖 Telegram Media Bot (Ultimate Edition)

一款 **全异步、高性能、本地化** 的 Telegram 媒体管理与搬运机器人。
专为高并发社群设计，集成智能去重、内容净化、自动转发、相册合并、信誉体系、防刷屏等工业级功能。

---

## 🚀 核心架构优势 (Performance)

### ⚡️ **异步并发与读写分离**
* **AsyncIO + aiosqlite**: 全流程非阻塞 I/O，完美支持 WAL 模式，读写锁分离技术让查询性能提升数倍。
* **内存级缓存 (TTLCache)**: 针对规则、替换词、管理员列表引入 60s 级内存缓存，大幅降低磁盘 I/O 压力。
* **智能队列工人**: 所有的转发任务均通过后台工人处理。支持精确到秒的 **随机延迟转发**，即使首条消息也能完美遵循延迟规则，有效规避平台风控。

### 🛡️ **安全与防御 (Security)**
* **ReDoS 预防**: 对管理员自定义正则进行长度与复杂度双重校验，防止正则表达式拒绝服务攻击。
* **防刷屏控流**: 基于用户 ID 的滑动窗口计数器，自动惩罚在一分钟内狂发媒体的恶意用户。
* **权限并集体系**: 融合 `.env` 静态配置与数据库动态管理员，确保权限管理的灵活性与安全性。

---

## ✨ 独家特色功能 (Features)

### 📁 **全媒体类型支持 (Full Media Support)**
* **覆盖全场景**: 不再局限于图片和视频。新增对 **文件 (Document)、音频 (Audio)、语音 (Voice)、视频消息 (Video Note) 以及 贴纸 (Sticker)** 的全面支持。
* **深度净化**: 所有支持的媒体类型在转发时均会通过净化引擎，自动剥离原始转发来源，并根据频道规则重写文案。

### 🔄 **消息联动编辑同步 (Edit Sync)**
* **无缝同步**: 当群组内的消息说明（Caption）被修改时，Bot 会自动检索所有已转发的目标频道，并同步调用 API 修改对应的文案，确保信息的一致性。

### 🎖️ **社群信誉自治 (Karma System)**
* **动态白名单**: 利用内置投票系统，自动累计用户的 Upvote/Downvote 净值。信誉极佳的用户将自动获得白名单豁免，免除内容审查。

### 🛡️ **强制剧透马赛克 (Spoiler Enforcement)**
* **合规检查**: 支持 `require_spoiler` 规则。若启用，所有未手动勾选“隐藏媒体”或未携带 `#nsfw` 标签的媒体将被自动拦截，确保频道内容合规。

### 📊 **本地运营周报 (Local Analytics)**
* **数据闭环**: 每周日晚 20:00 自动生成纯文本活跃度报告。完全基于 SQLite 本地聚合查询，无需任何外部 API。

### 💀 **死信队列管理 (DLQ Manager)**
* **容错恢复**: 针对因 403 (被踢出) 或 400 (格式错误) 导致失败的任务，自动移入 `dead_letter_queue`。支持管理员通过 `/dlq` 查看并使用 `/retrydlq` 一键重试。

---

## 🛠 快速开始 (Deployment)

### 1. 一键安装并运行 (推荐)
适用于 Ubuntu/Debian 服务器。该脚本将自动安装系统依赖（Python, Git 等）、配置环境、并可选安装为 Systemd 服务实现开机自启。
```bash
curl -sSL https://raw.githubusercontent.com/JaikChen/telegram-media-bot/master/install.sh | bash
```

### 2. 日常维护 (Maintenance)
项目脚本已统一整理至 `scripts/` 目录：
* **更新并重启**: `bash scripts/deploy.sh` (同步 GitHub 代码、更新依赖并平滑重启)
* **彻底重装**: `bash scripts/reinstall.sh` (保留 `.env` 配置，清空其余数据并重新拉取代码)

### 3. Docker 部署
```bash
docker-compose up -d --build
```

---

## 📖 详细文档
* [使用手册 (Manual)](docs/manual.md) - 包含转发配置、清洗规则说明及完整指令表。
* [开发者指南 (Developer)](GEMINI.md) - 架构设计与开发规范。


---

## 📖 扩展命令手册 (Admin Commands)

| 指令 | 描述 |
| :--- | :--- |
| `/queue` | 📊 查看积压转发队列状态 (实时监控) |
| `/listall` | 📋 一键查询所有已配置的转发链 |
| `/dlq` | 查看死信队列中最近失败的任务 |
| `/retrydlq {id\|all}` | 从死信队列恢复并重试任务 |
| `/cleardlq` | 清空死信队列 |
| `/setdelay min max` | 设置转发任务的随机延迟范围 |
| `/repair` | 手动唤醒可能卡死的转发工人 |
| `/setvoting on/off` | 为当前频道开启/关闭 👍👎 投票按钮 |


---

## 📂 模块化结构

* `db.py`: 数据库单例，包含读写锁逻辑与业务查询。
* `cleaner.py`: 核心净化引擎，包含 ReDoS 防御与标签回填。
* `handlers/media.py`: 媒体处理器，包含 **Debounce (防抖) 相册收集** 逻辑。
* `handlers/extras.py`: 包含编辑同步、周报生成、防刷屏等扩展逻辑。
* `locales.py`: 国际化与提示语模板。

📄 **License**: MIT. 基于纯本地化理念开发，不依赖任何第三方 AI 接口。
