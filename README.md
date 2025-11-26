


# 🤖 Telegram Media Bot (全能版)


一款功能强大的 Telegram 群组/频道媒体管理机器人。专为净化社群环境、自动化转发和媒体管理而设计。支持自定义规则清理、媒体去重、自动转发、互动投票等高级功能。

-----

## ✨ 核心特性

### 🛡️ 内容净化与管理

  * **智能清理**：自动去除照片/视频说明中的广告、链接、@引用等。
  * **规则灵活**：支持正则匹配、关键词屏蔽、长度限制、替换词等多种策略。
  * **白名单机制**：允许特定用户（如赞助者）发送带链接的媒体而不被清理。
  * **自定义页脚**：在清理后的媒体说明中自动追加自定义的小尾巴（如频道推广链接）。

### 🚀 自动化与转发

  * **自动转发**：支持多对多的转发映射（源频道 -\> 目标频道），转发时自动应用清理规则。
  * **智能去重**：
      * 基于媒体指纹（`file_unique_id`）识别重复内容。
      * **滚动清理**：自动保留最近 1 年的去重记录，过期数据自动清理，防止数据库无限膨胀。
  * **相册支持**：完美支持 Media Group（相册），转发时保留首条说明并自动去重。

### 🎮 互动与控制

  * **互动投票**：转发单张图片/视频时，自动附加 👍 / 👎 投票按钮。
  * **静音模式**：支持 `quiet`（完全静音）和 `autodel`（阅后即焚）模式，避免 Bot 回复刷屏。
  * **权限隔离**：
      * **Super Admin**：拥有所有权限（系统维护、数据库管理）。
      * **Chat Admin**：仅能管理其所在的频道/群组。

### 🛠️ 系统维护

  * **日志频道**：将清理记录、错误报警实时推送到指定频道。
  * **数据库维护**：支持一键备份/恢复，每日凌晨 4:00 自动清理过期数据并整理碎片。
  * **无效群组清理**：自动检测并移除 Bot 被踢出的群组数据。

-----

## 🛠 环境与依赖

  * **操作系统**: Linux (推荐 Ubuntu/Debian/CentOS)
  * **Python**: 3.11 或更高版本
  * **数据库**: SQLite (零配置，自动生成 `bot.db`)

-----

## 🚀 快速部署

### 方法一：一键脚本部署 (推荐)

我们提供了一个全自动部署脚本，会自动配置虚拟环境、安装依赖并注册 systemd 服务。

1.  **克隆仓库**

    ```bash
    git clone https://github.com/你的用户名/telegram-media-bot.git
    cd telegram-media-bot
    ```

2.  **配置环境变量**
    创建 `.env` 文件并填入你的 Bot Token 和管理员 ID：

    ```bash
    echo "BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11" > .env
    # 多个管理员ID用逗号分隔
    echo "ADMIN_IDS=123456789,987654321" >> .env
    ```

3.  **运行部署脚本**

    ```bash
    chmod +x deploy_bot.sh
    sudo ./deploy_bot.sh
    ```

    *脚本会自动创建 Python 虚拟环境、安装依赖、创建 systemd 服务并启动 Bot。*

4.  **查看日志**

    ```bash
    sudo journalctl -u telegram-media-bot -f
    ```

### 方法二：手动运行

1.  **安装依赖**

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **启动 Bot**

    ```bash
    python main.py
    ```

-----

## 📖 使用指南

> 💡 **提示**：
>
>   * 大部分命令需要在 Bot **所在的群组/频道**中使用，或者在**私聊**中指定 `-100频道ID`。
>   * 建议在私聊中操作，以保护隐私。

### 1\. 身份与权限

| 角色 | 描述 | 权限范围 |
| :--- | :--- | :--- |
| **Super Admin** | 在 `.env` 中配置的 `ADMIN_IDS` | **全权掌控**。可管理所有频道、系统设置、数据库维护。 |
| **Chat Admin** | 所在群组/频道的管理员 | **仅限当前频道**。可修改规则、关键词、页脚等配置。 |

-----

### 2\. 基础规则配置 (Rules)

控制 Bot 如何处理媒体说明文字。

  * **设置规则** (覆盖式)：
    ```bash
    /setrules -100123456789 clean_links,remove_at_prefix
    ```
  * **添加/删除单条规则**：
    ```bash
    /addrule -100123456789 block_keywords
    /delrule -100123456789 maxlen:50
    ```
  * **查看/清空规则**：
    ```bash
    /listrules -100123456789
    /clearrules -100123456789
    ```

#### 📝 可用规则参数表

| 规则代码 | 功能描述 |
| :--- | :--- |
| `keep_all` | **保留所有**。跳过清理（但替换词和页脚仍生效）。 |
| `strip_all_if_links` | **严格模式**。如果说明中包含任何链接（含文字链），直接删除整段说明。 |
| `clean_links` | **温和模式**。仅删除说明中的 URL 文本，保留其他文字。 |
| `remove_at_prefix` | **去引用**。删除所有 `@username` 格式的文本。 |
| `block_keywords` | **关键词屏蔽**。需配合 `/addkw` 使用。命中关键词则删除整段说明。 |
| `maxlen:50` | **长度限制**。超过 50 个字符则删除整段说明。 |

-----

### 3\. 内容增强 (Content)

让你的频道内容更规范、更丰富。

#### 🔑 关键词屏蔽

  * **添加屏蔽词** (支持正则)：
    ```bash
    /addkw -100xxx 赌博
    /addkw -100xxx \d{11} regex  # 屏蔽手机号正则
    ```
  * **管理屏蔽词**：
    ```bash
    /listkw -100xxx
    /delkw -100xxx 赌博
    ```

#### 🔄 关键词替换

自动将文案中的 A 替换为 B（例如将搬运来源替换为自己的频道）。

  * **添加替换**：
    ```bash
    /addreplace -100xxx 原频道 @MyChannel
    ```

#### 📝 自定义页脚

在清理后的说明文字末尾，自动追加一段文字。

  * **设置页脚**：
    ```bash
    /setfooter -100xxx 📢 关注我们：@MyChannel
    ```

#### 🛡 用户白名单

允许特定用户（如赞助者、管理员小号）发送带链接/广告的媒体而不被 Bot 清理。

  * **添加白名单**：
    ```bash
    /allowuser -100xxx 123456789
    ```

-----

### 4\. 🎮 控制与模式 (Control)

优化 Bot 的交互体验。

#### 🔕 静音与阅后即焚模式

防止 Bot 的回复刷屏。

```bash
/setquiet -100xxx autodel
```

  * `off`: **正常** (默认)，Bot 对每个操作都回复 "✅ 已..."。
  * `quiet`: **静音**，操作成功时不说话，仅报错时回复。
  * `autodel`: **阅后即焚**，Bot 回复成功消息，但 **10秒后自动删除** 该消息。

#### 👍 互动投票开关

开启后，Bot 转发单张图片/视频时，会自动在下方附加 👍 / 👎 按钮。

```bash
/setvoting -100xxx on
```

#### 🔒 锁定与解锁

暂停 Bot 对该频道的清理工作（如维护期间）。

```bash
/lock -100xxx
/unlock -100xxx
```

-----

### 5\. 🔁 自动转发 (Forward)

建立频道间的自动搬运机制。

  * **添加转发关系**：

    ```bash
    /addforward -100源频道ID -100目标频道ID
    ```

    *当源频道发布媒体时，Bot 会自动清理并转发到目标频道。*

  * **查看/删除转发**：

    ```bash
    /listforward -100源频道ID
    /delforward -100源频道ID -100目标频道ID
    ```

-----

### 6\. ⚙️ 系统管理 (Super Admin)

> ⚠️ **仅限固定管理员使用**

  * **📝 日志频道**：设置一个频道用于接收 Bot 的运行日志（去重记录、错误报警）。
    ```bash
    /setlog -100日志频道ID
    ```
  * **🧹 清理无效群组**：清理数据库中 Bot 被踢出或已解散的群组数据。
    ```bash
    /cleanchats
    ```
  * **💾 数据库维护**：
      * `/backupdb`: 获取 `bot.db` 文件备份。
      * `/restoredb`: 回复此命令并附带数据库文件进行恢复。
      * `/cleandb`: 手动触发数据库清理（删除 1 年前的去重记录）并执行 VACUUM 整理。
  * **👑 管理员管理**：
      * `/addadmin 123456`: 添加动态管理员。
      * `/listadmins`: 查看所有管理员列表。

-----

## 📊 数据库自动维护策略

Bot 内置了智能的数据库维护机制，无需人工干预：

1.  **去重记录 (TTL)**：
      * Bot 默认保留 **1 年 (365天)** 的媒体去重指纹。
      * 超过 1 年的记录会被自动删除，允许老图重发。
2.  **每日维护任务**：
      * 每天 **UTC 04:00** 自动运行。
      * 执行内容：清理过期数据 + `VACUUM` (释放磁盘空间)。

-----

## 📁 项目结构

```plaintext
telegram-media-bot/
├── main.py               # 程序主入口，负责启动和调度
├── db.py                 # 数据库核心逻辑 (SQLite封装)
├── cleaner.py            # 文本清理核心算法 (正则/替换)
├── config.py             # 配置文件读取
├── handlers/             # 功能模块文件夹
│   ├── utils.py          # 通用工具与权限检查
│   ├── sys_admin.py      # 系统级管理命令
│   ├── chat_mgmt.py      # 群组级配置命令
│   ├── info.py           # 信息查询与帮助
│   ├── media.py          # 媒体消息处理与转发逻辑
│   └── callback.py       # 按钮回调处理 (投票)
├── requirements.txt      # Python 依赖清单
├── deploy_bot.sh         # 一键部署脚本
└── update-local.sh       # 更新脚本
```

-----

## ❓ 常见问题 (FAQ)

**Q: Bot 没有反应怎么办？**
A: 1. 检查 Bot 是否是群组管理员。2. 检查 `.env` 中 Token 是否正确。3. 查看日志 `journalctl -u telegram-media-bot -f`。

**Q: 如何获取频道 ID？**
A: 将 Bot 拉入频道，随便发一条消息，转发给 `@userinfobot` 或查看 Bot 后台日志。频道 ID 通常以 `-100` 开头。

**Q: 为什么相册没有投票按钮？**
A: Telegram API 限制，发送 Media Group (相册) 时无法附加 Inline Keyboard 按钮。投票功能仅对单张图片/视频生效。

**Q: 日志报错 `Can't parse entities`？**
A: 这是 Markdown 格式错误。请确保使用了最新版的代码（已修复 Markdown 解析问题），重启 Bot 即可。

-----

## 📜 许可证

本项目采用 [MIT License](https://www.google.com/search?q=LICENSE) 开源。欢迎 Fork 和提交 PR！