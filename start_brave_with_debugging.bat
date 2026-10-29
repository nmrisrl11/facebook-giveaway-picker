@echo off
title Launch Brave for Facebook Giveaway Picker
echo =======================================================
echo   Launching Brave with Remote Debugging (Port 9222)
echo =======================================================
echo.
echo NOTE: If Brave is already running, please close all Brave
echo windows first so the debugging port can attach properly.
echo.

set "BRAVE_PATH=C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
if not exist "%BRAVE_PATH%" (
    set "BRAVE_PATH=%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"
)

if not exist "%BRAVE_PATH%" (
    echo [ERROR] Could not find brave.exe automatically.
    echo Please make sure Brave is installed.
    pause
    exit /b 1
)

echo Starting Brave from: "%BRAVE_PATH%" ...
start "" "%BRAVE_PATH%" --remote-debugging-port=9222

echo.
echo Brave has been launched with port 9222 enabled!
echo You can now run run_picker.bat anytime.
echo.
timeout /t 5
