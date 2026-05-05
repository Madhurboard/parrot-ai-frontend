@echo off
title Cloudflare Tunnel - Parrot AI
color 0B
echo ================================================
echo   Starting Cloudflare Tunnel for Parrot AI
echo   Target: http://localhost:8000
================================================
echo.

:: Check if cloudflared is in PATH
where cloudflared >nul 2>nul
if %errorlevel% equ 0 (
    set CLOUDFLARE_CMD=cloudflared
    goto :START
)

:: Check common winget install path (64-bit)
if exist "C:\Program Files\cloudflared\cloudflared.exe" (
    set CLOUDFLARE_CMD="C:\Program Files\cloudflared\cloudflared.exe"
    goto :START
)

:: Check common winget install path (32-bit)
if exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" (
    set CLOUDFLARE_CMD="C:\Program Files (x86)\cloudflared\cloudflared.exe"
    goto :START
)

echo [ERROR] cloudflared is not installed or not in PATH.
echo [ACTION] Please RESTART your terminal or check installation.
echo.
pause
exit /b

:START
echo [LAUNCH] Starting tunnel using: %CLOUDFLARE_CMD%
echo [INFO] Look for a URL like: https://xxx.trycloudflare.com
echo.
%CLOUDFLARE_CMD% tunnel --url http://localhost:8000

pause
