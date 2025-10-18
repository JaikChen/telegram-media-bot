# Telegram 媒体说明清理机器人

一款基于 Python & SQLite 的 Telegram 群组/频道媒体说明文字清理机器人，支持自定义规则、关键词屏蔽、相册合并与去重，提供私聊命令全方位管理和统计，同时附带一键部署脚本和~~自动化更新方案~~一键更新脚本。仅需使用telegram bot Token。
~~其实是没有申请下来API，之前有API的账号爆掉了~~
---

## 目录

1. [特性](#特性)  
2. [环境与依赖](#环境与依赖)  
3. [项目结构](#项目结构)  
4. [快速开始](#快速开始)  
5. [本地调试](#本地调试)  
6. [部署](#部署)  
7. [一键更新](#一键更新)  
8. [私聊命令](#私聊命令)  
9. [常见问题](#常见问题)  
10. [贡献与许可](#贡献与许可)  

---

## 特性

-   **自动清理**：照片/视频说明文字，支持链接、`@` 前缀、关键词屏蔽、长度限制等  
-   **相册合并**：延迟处理，保留第一条清理后的说明  
-   **去重机制**：防止重复转发同一媒体  
-   **私聊管理**：规则、关键词、锁定/解锁、统计、数据库备份/恢复  
-   **轻量存储**：SQLite 单文件数据库，自动建表  
-   **后台守护**：支持 systemd 后台运行与开机自启  
-   **一键部署**：自带 `deploy_bot.sh` 脚本，简化环境准备  
-   **一键更新**：提供  `update-local.sh`脚本，简化拉库更新

---

## 环境与依赖

-   **操作系统**：Linux（CentOS/RHEL、Ubuntu/Debian 均可）  
-   **Python**：3.9 及以上（推荐 3.11）  
-   **SQLite**：内置，无需额外安装  
-   **必装工具**：`git`, `sudo`  
-   **Python 包**：见 `requirements.txt`  
    ```txt
    python-telegram-bot==20.7
    python-dotenv
    ```

---

## 项目结构

```plaintext
telegram-media-bot/
├── handlers/
│   ├── commands.py      # 私聊命令处理
│   └── media.py         # 群组/频道媒体处理
├── cleaner.py           # 说明文字清理逻辑
├── config.py            # 环境与常量配置
├── db.py                # SQLite 数据库操作
├── main.py              # Bot 启动与路由注册
├── requirements.txt     # 依赖清单
├── .env                 # 环境变量文件（BOT_TOKEN）
├── bot.db               # SQLite 数据库文件（首次运行生成）
└── deploy_bot.sh        # 一键部署脚本
```

---

## 快速开始
（如果你想自己搭建）
1. 克隆仓库  
   ```bash
   git clone https://github.com/JaikChen/telegram-media-bot.git
   cd /opt/telegram-media-bot
   ```

2. 配置环境变量  
（也可以在项目文件夹里放置一个.env文件）
   ```bash
   echo "BOT_TOKEN=你的TelegramBotToken" > .env
   ```

3. 赋予脚本执行权限并运行  
   ```bash
   chmod +x deploy_bot.sh
   sudo ./deploy_bot.sh
   ```

4. 查看运行日志  
   ```bash
   journalctl -u telegram-media-bot -f
   ```

---

## 本地调试

1. 创建并激活虚拟环境  
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

2. 安装依赖  
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. 启动 Bot  
   ```bash
   python main.py
   ```
   首次启动会自动创建 `bot.db` 并初始化表结构，控制台显示日志。

---

## 部署

### 一键部署脚本

根目录的 `deploy_bot.sh` 会自动：

1. 进入项目目录  
2. 删除并重建 `.venv`  
3. 安装依赖  
4. 校验 `.env`  
5. 生成 systemd 服务文件  
6. 启用并启动服务  

赋权并运行：

```bash
chmod +x deploy_bot.sh
sudo ./deploy_bot.sh
```

脚本内容（纯 LF 格式）：

```bash
#!/bin/bash
set -e

APP_DIR="/opt/telegram-media-bot"
VENV_DIR="$APP_DIR/.venv"
SERVICE_FILE="/etc/systemd/system/telegram-media-bot.service"

echo "🚀 部署开始..."

cd $APP_DIR

# 重建虚拟环境
[[ -d $VENV_DIR ]] && rm -rf $VENV_DIR
python3.11 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# 安装依赖
pip install --upgrade pip
pip install python-telegram-bot==20.7 python-dotenv

# 检查 .env
[[ ! -f .env ]] && echo "⚠️ .env 缺失" && exit 1

# 写入 systemd 服务
sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Telegram Media Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/python $APP_DIR/main.py
EnvironmentFile=$APP_DIR/.env
Restart=always
RestartSec=5
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable telegram-media-bot
sudo systemctl restart telegram-media-bot

echo "✅ 部署完成！日志: journalctl -u telegram-media-bot -f"
```

---

### 手动部署

1. 编辑 systemd 服务：  
   `/etc/systemd/system/telegram-media-bot.service`
   ```ini
   [Unit]
   Description=Telegram Media Bot
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/opt/telegram-media-bot
   ExecStart=/opt/telegram-media-bot/.venv/bin/python /opt/telegram-media-bot/main.py
   EnvironmentFile=/opt/telegram-media-bot/.env
   Restart=always
   RestartSec=5
   User=root
   Group=root

   [Install]
   WantedBy=multi-user.target
   ```

2. 启动服务：
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable telegram-media-bot
   sudo systemctl start telegram-media-bot
   ```

3. 查看日志：
   ```bash
   sudo journalctl -u telegram-media-bot -f
   ```

---

## 一键更新

### 一键拉取GitHub仓库并重新启动
把仓库里的update-local.sh丢到上一级文件夹然后授权运行。
```bash
chmod +x deploy_bot.sh
sudo ./deploy_bot.sh
```

---

## 私聊命令

> **仅限管理员（固化 + 动态）使用**

### 1. 规则管理

- **/setrules `<频道ID> 规则1,规则2,...`**  
  覆盖式设置所有清理规则  
  示例：  
  ```
  /setrules -100123456789 clean_links,remove_at_prefix,block_keywords,maxlen:80
  ```

- **/addrule `<频道ID> 规则`**  
  在现有规则末尾追加  
  示例：  
  ```
  /addrule -100123456789 maxlen:100
  ```

- **/delrule `<频道ID> 规则`**  
  删除指定规则  
  示例：  
  ```
  /delrule -100123456789 clean_links
  ```

- **/listrules `<频道ID>`**  
  列出所有规则  
  示例：  
  ```
  /listrules -100123456789
  ```

- **/clearrules `<频道ID>`**  
  清空所有规则  
  示例：  
  ```
  /clearrules -100123456789
  ```

> **可用规则**：  
> `clean_links`、`strip_all_if_links`、`remove_at_prefix`、`block_keywords`、`keep_all`、`maxlen:<N>`

---

### 2. 关键词管理

- **/addkw `<频道ID> 关键词 [regex]`**  
  添加关键词，可选正则模式  
  示例：  
  ```
  /addkw -100123456789 广告
  /addkw -100123456789 \d{11} regex
  ```

- **/listkw `<频道ID>`**  
  列出所有关键词  
  示例：  
  ```
  /listkw -100123456789
  ```

- **/delkw `<频道ID> 关键词`**  
  删除指定关键词  
  示例：  
  ```
  /delkw -100123456789 广告
  ```

- **/exportkw `<频道ID>`**  
  导出关键词为文本文件  
  示例：  
  ```
  /exportkw -100123456789
  ```

- **/importkw `<频道ID> 词1,词2,...`** 或回复文件后执行  
  批量导入关键词  
  示例：  
  ```
  /importkw -100123456789 广告,推广,微信
  ```

---

### 3. 锁定 / 解锁

- **/lock `<频道ID>`**：暂停该频道所有清理  
- **/unlock `<频道ID>`**：恢复清理  

示例：  
```
/lock -100123456789
/unlock -100123456789
```

---

### 4. 查询与统计

- **/listchats**：列出 Bot 当前所在所有频道和群组  
- **/chatinfo `<频道ID>`**：查看频道名称与当前规则  
- **/preview `<频道ID> 文本>`**：预览文本按规则处理后的结果  
- **/stats**：查看各频道已清理媒体总次数  
- **/help**：显示帮助菜单  

---

### 5. 管理员 & 数据库

- **/addadmin `<用户ID>`**：添加动态管理员  
- **/deladmin `<用户ID>`**：删除动态管理员  
- **/listadmins**：列出固化 + 动态管理员  
- **/backupdb**：导出 SQLite 数据库  
- **/restoredb**（回复文件后执行）：恢复数据库  

---

## 常见问题

- **No module named 'telegram'**  
  激活 `.venv` 并执行：  
  ```bash
  pip install python-telegram-bot==20.7
  ```

- **无法安装 20.x 版本**  
  确认 `python3 --version` ≥ 3.9。

- **SQLite 锁表或性能问题**  
  可考虑使用 `aiosqlite` 或迁移到 MySQL/PostgreSQL。

---

## 贡献与许可

欢迎提出 Issue 与 Pull Request，共同完善功能。  
本项目遵循 MIT 许可证，详见 [LICENSE](LICENSE)。
