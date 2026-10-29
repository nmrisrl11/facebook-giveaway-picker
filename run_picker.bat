@echo off
title Facebook Giveaway Picker
cd /d "%~dp0"

echo =======================================================
echo           FACEBOOK GIVEAWAY WINNER PICKER
echo =======================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [!] Virtual environment not found. Creating .venv...
    python -m venv .venv
    echo [!] Installing required packages...
    .venv\Scripts\pip install -r requirements.txt
)

.venv\Scripts\python.exe giveaway_picker.py

echo.
pause
