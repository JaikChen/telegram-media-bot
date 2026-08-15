# 🤖 Telegram Media Bot (Ultimate Edition)

一款 **全异步、高并发、工业级** 的 Telegram 媒体搬运与内容净化机器人。
专为频道、群组及私聊搬运设计，集成 **源频道人工转发去源**、**全链路级联转发**、**整行广告深度拦截**、**相册原子聚合**、**死信队列恢复** 与 **信誉自治体系**。

---

## 🌟 核心功能一览

### 1. 🔄 **智能去源与级联转发 (Forwarding & De-sourcing)**
- **源频道人工转发自动去源**：向源频道人工转发带有来源的媒体时，Bot 会自动提取媒体、清洗广告并以频道身份重新发布纯净无源版本，同时自动删除带来源的人工转发原消息。
- **私聊转发即时去源**：在私聊中将任何媒体转发给 Bot，Bot 立即返回去除来源、清除广告后的独立媒体。
- **全链路级联分发**：支持 `A -> B -> C` 多层级自动穿透转发，自动拓扑解析，规避循环死锁。
- **随机防封延迟**：支持 `/setdelay min max` 设置消息随机间隔（秒），平滑请求速率。
- **队列管理与监控**：支持 `/queue` 实时查看积压队列，`/clearqueue` 一键清空积压，`/pause` 与 `/resume` 暂停/恢复调度。

### 2. 🛡️ **工业级广告拦截引擎 (Ad Cleaner Engine)**
- **整行广告清除 (`strip_ad_lines` / `clean_lines`)**：凡是包含 URL 链接、`@` 账号提及、引流话术（如 `评论区看全集`、`置顶看完整版`、`提取码在评论区`）或自定义关键词的行，直接整行剔除，保留其他正常描述。
- **智能删链 (`clean_links`)** 与 **严格删链 (`strip_all_if_links`)**：支持清除 Markdown 嵌入超链接、Telegram TextLink 实体链接及各类 URL。
- **隐形字符清洗**：自动过滤零宽字符、从右到左控制符等 24 种隐形欺骗字符。
- **关键词模式**：支持普通字词与正则表达式 (`/addkw`)，提供温和按行过滤 (`clean_keywords`) 与严格整条清空 (`block_keywords`)。
- **文本替换与页脚**：支持全局或单频道关键词替换 (`/addreplace`) 与自定义尾巴 (`/setfooter`)。

### 3. 📦 **全媒体格式与相册支持 (Media & Album)**
- **全格式覆盖**：支持图片 (Photo)、视频 (Video)、动图 (Animation)、文件 (Document)、音频 (Audio)、语音 (Voice)、视频圆视频 (Video Note)、贴纸 (Sticker)。
- **相册 (MediaGroup) 原子聚合**：通过滑动时间窗口（Debounce）聚合相册内所有分卷，统一清洗文案后打包发送，保证相册完整性与顺序。

### 4. ⚡️ **高可用与健壮架构 (Reliability & Performance)**
- **单实例文件锁**：防止多进程并发启动抢占 Telegram 轮询冲突。
- **防回环出站过滤**：出站消息统一指纹记录，彻底杜绝 Bot 自身消息回环扩散。
- **死信队列 (DLQ)**：因网络抖动、频控或权限失效失败的任务自动沉降至 DLQ，支持 `/dlq` 查看、`/retrydlq` 重试或 `/repair` 修复。
- **WAL 模式 SQLite**：全异步 `aiosqlite` 操作，兼具轻量化与高并发读写性能。

---

## 🚀 快速开始 (Quick Start)

### 环境要求
- **Python 3.10+** (推荐 3.11 / 3.12 / 3.14)
- **Windows / Linux / macOS**

### 1. 配置环境变量
在项目根目录下创建 `.env` 文件（可参考配置如下）：
```env
BOT_TOKEN=8224286324:AAGyNgFIbMCE2Vb_VWneeFgmQXYIvxkUkJY
ADMIN_ID=7975947295
DATABASE_PATH=data/bot.db
PROXY_URL=socks5://127.0.0.1:7891
LOG_LEVEL=INFO
```

### 2. 启动与管理脚本 (Windows 一键批处理)
- **环境初始化**：双击运行 `setup_env.bat`（自动创建虚拟环境并安装依赖包）。
- **运行机器人**：双击运行 `start_bot.bat`（自动检查环境并启动 Bot）。
- **运行单元测试**：双击运行 `run_tests.bat`（运行 pytest 全量测试集）。

---

## 📜 完整指令手册 (Command Reference)

### 1. 🔁 转发管理
| 指令 | 说明 | 示例 |
| :--- | :--- | :--- |
| `/addforward <源ID> <目标ID>` | 建立频道/群组转发映射 | `/addforward -100111 -100222` |
| `/delforward <源ID> <目标ID>` | 解除转发映射 | `/delforward -100111 -100222` |
| `/listforward <源ID>` | 查看指定源频道的转发链路 | `/listforward -100111` |
| `/listall` | 一键查询当前配置的所有转发链 | `/listall` |

---

### 2. 🧩 规则与内容过滤 (`/addrule`, `/setrules`)
支持为指定频道设置规则，或使用 `all` 参数批量配置所有频道。

| 规则参数 | 作用说明 |
| :--- | :--- |
| `strip_ad_lines` | **整行广告清除**：凡含链接、@提及、引流句式或关键词的行整行删除 |
| `clean_keywords` | **温和屏蔽**：仅删除包含关键词的行 |
| `block_keywords` | **严格屏蔽**：只要发现关键词则直接删除整条文案 |
| `clean_links` | **智能删链**：去除链接但保留正常说明文字 |
| `strip_all_if_links` | **严格删链**：只要发现链接则整条文案清空 |
| `remove_at_prefix` | 去除 `@` 账号与群组引用 |
| `pangu` | 中英文排版美化（在中英文之间自动补齐空格） |
| `keep_all` | 保留所有文案不作过滤 |
| `maxlen:N` | 限制文案最大字符长度（如 `maxlen:100`） |

**规则配置指令：**
- `/addrule <频道ID|all> <规则>`：添加规则（如 `/addrule all strip_ad_lines`）
- `/delrule <频道ID|all> <规则>`：删除单条规则
- `/setrules <频道ID|all> <规则1> <规则2>`：覆盖重置规则
- `/clearrules <频道ID|all>`：清空规则
- `/listrules <频道ID>`：查看当前规则

---

### 3. 🛠 关键词、替换与页脚
- `/addkw <频道ID|all> 词1 词2 ...`：添加屏蔽关键词（末尾加 `regex` 可启用正则）
- `/delkw <频道ID|all> 词`：删除指定屏蔽词
- `/listkw <频道ID>`：查看关键词列表
- `/addreplace <频道ID|all> <旧内容> <新内容>`：添加文案替换规则
- `/delreplace <频道ID|all> <旧内容>`：删除文案替换规则
- `/setfooter <频道ID|all> <内容>`：设置消息底部固定页脚
- `/delfooter <频道ID|all>`：删除消息页脚

---

### 4. ⚙️ 系统运维与队列管理 (Super Admin)
- `/queue`：查看当前待转发队列各频道积压统计
- `/clearqueue [all|频道ID]`：**一键清空待转发积压队列**
- `/dlq`：查看发送失败的任务死信队列
- `/cleardlq`：清空死信队列
- `/retrydlq [ID|all]`：重新投递死信队列任务
- `/repair`：重置并修复卡顿的队列状态
- `/pause`：暂停转发工人（积压保留）
- `/resume`：恢复转发工人
- `/setdelay <min> <max>`：设置转发随机延迟秒数（如 `/setdelay 10 60`）
- `/stats`：查看各频道累计处理统计
- `/addadmin <用户ID>` / `/deladmin <用户ID>` / `/listadmins`：管理动态管理员

---

## 🧪 自动化测试 (Testing)

项目采用 `pytest` + `pytest-asyncio` 进行全模块单元测试：
```bash
# 激活环境并运行全量测试
pytest -v
```
测试覆盖：
- 规则清洗引擎与整行广告检测 (`test_cleaner.py`)
- 队列清空与重试机制 (`test_clear_queue.py`)
- 全局去重与相册聚合防回环 (`test_dedup_and_album.py`)
- 延迟调度与速率控制 (`test_pacing.py`)
- 频道人工转发去源、私聊去源与级联分发 (`test_refactored_system.py`)

---

## 📄 License
MIT License
