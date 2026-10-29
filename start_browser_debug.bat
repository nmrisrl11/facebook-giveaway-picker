@echo off
title Launch Browser with Remote Debugging
echo =======================================================
echo     Launch Browser with Remote Debugging (Port 9222)
echo      Developed by Nomer Israel (@nmrisrl11)
echo =======================================================
echo.
echo NOTE: If your browser is already open, please close all
echo windows of that browser first so the debugging port can attach.
echo.
echo Which browser do you want to launch?
echo   [1] Brave Browser
echo   [2] Google Chrome
echo   [3] Microsoft Edge
echo.
set /p choice="Enter choice [1-3] (Default 1): "
if "%choice%"=="" set choice=1

if "%choice%"=="1" (
    set "EXE_NAME=Brave"
    set "BROWSER_PATH=C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
    if not exist "%BROWSER_PATH%" set "BROWSER_PATH=%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"
)
if "%choice%"=="2" (
    set "EXE_NAME=Chrome"
    set "BROWSER_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not exist "%BROWSER_PATH%" set "BROWSER_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    if not exist "%BROWSER_PATH%" set "BROWSER_PATH=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
)
if "%choice%"=="3" (
    set "EXE_NAME=Edge"
    set "BROWSER_PATH=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not exist "%BROWSER_PATH%" set "BROWSER_PATH=C:\Program Files\Microsoft\Edge\Application\msedge.exe"
)

if not exist "%BROWSER_PATH%" (
    echo [ERROR] Could not find executable for %EXE_NAME%.
    echo Please make sure the browser is installed.
    pause
    exit /b 1
)

echo Starting %EXE_NAME% from: "%BROWSER_PATH%" with port 9222...
start "" "%BROWSER_PATH%" --remote-debugging-port=9222 --restore-last-session --disable-session-crashed-bubble

echo.
echo Browser launched with port 9222 enabled!
echo You can now run run_picker.bat.
echo.
timeout /t 4
