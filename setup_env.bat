@echo off
chcp 65001 >nul
title Setup Python Environment
cd /d "%~dp0"

echo ====================================================
echo   Telegram Media Bot - Python Environment Setup
echo ====================================================

set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"

if exist "%UV_EXE%" (
    echo [*] Found uv at %UV_EXE%
    echo [*] Creating virtual environment with uv...
    "%UV_EXE%" venv .venv
    echo [*] Installing dependencies with uv...
    "%UV_EXE%" pip install -r requirements.txt --python .venv\Scripts\python.exe
) else (
    echo [*] uv not found, using Python launcher / standard venv...
    py -3.14 -m venv .venv 2>nul || py -3 -m venv .venv 2>nul || python -m venv .venv
    echo [*] Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo.
echo [✓] Environment setup completed successfully!
echo.
pause
