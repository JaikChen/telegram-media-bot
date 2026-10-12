@echo off
chcp 65001 >nul
title Telegram Media Bot (Instance 2)
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [!] Virtual environment not found. Running setup...
    call setup_env.bat
)

echo [*] Starting Telegram Media Bot (Instance 2)...
".venv\Scripts\python.exe" src/main.py --instance bot2 %*
pause
