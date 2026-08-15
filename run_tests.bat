@echo off
chcp 65001 >nul
title Run Tests - Telegram Media Bot
cd /d "%~dp0"

echo [*] Running pytest suite...
".venv\Scripts\pytest.exe" -v
pause
