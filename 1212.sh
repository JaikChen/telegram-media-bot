#!/bin/bash

# 一键清除 Git 历史记录并保留当前文件内容（适用于 master 分支）

echo "🚀 开始清理 Git 历史记录..."

# 创建一个新的分支（没有历史）
git checkout --orphan clean-master

# 添加所有文件
git add -A

# 提交当前状态
git commit -m "Clean commit with no history"

# 删除旧分支
git branch -D master

# 重命名新分支为 master
git branch -m master

# 强制推送到远程仓库
git push -f origin master

echo "✅ 历史记录已清除，当前文件已保留。"