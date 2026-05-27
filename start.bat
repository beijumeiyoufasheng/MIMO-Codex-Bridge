@echo off
chcp 65001 >nul
title MIMO Codex Bridge

echo ========================================
echo   MIMO Codex Bridge - Quick Start
echo ========================================
echo.

:input_key
set /p API_KEY="Enter your MIMO API Key (sk-xxxxx or tp-xxxxx): "
if "%API_KEY%"=="" (
    echo API Key cannot be empty!
    goto input_key
)

echo.
echo Select billing mode:
echo   1. Pay-as-you-go (sk-xxxxx)
echo   2. Token Plan (tp-xxxxx)
echo.
set /p MODE="Enter choice (1 or 2): "

if "%MODE%"=="2" (
    if not "%API_KEY:~0,3%"=="tp-" (
        echo Warning: Token Plan API Key should start with "tp-"
        pause
    )
)

echo.
echo Select thinking mode:
echo   1. Enable (recommended)
echo   2. Disable
echo.
set /p THINKING="Enter choice (1 or 2): "

set THINKING_FLAG=
if "%THINKING%"=="2" (
    set THINKING_FLAG=--no-thinking
)

echo.
echo ========================================
echo Starting proxy...
echo API Key: %API_KEY:~0,10%...
echo ========================================
echo.

python proxy.py --api-key %API_KEY% %THINKING_FLAG%

pause
