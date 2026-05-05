@echo off
title Cloudflare Tunnel - Parrot AI (Permanent)
color 0B
echo ================================================
echo   Starting PERMANENT Tunnel for Parrot AI
echo   URL: https://parrotai-be.madhur.me
echo   Target: http://localhost:8000
echo ================================================
echo.

set CLOUDFLARE_CMD="C:\Program Files (x86)\cloudflared\cloudflared.exe"

:: Check if cloudflared exists in path
if exist %CLOUDFLARE_CMD% (
    goto :START
)

:: Fallback to PATH
where cloudflared >nul 2>nul
if %errorlevel% equ 0 (
    set CLOUDFLARE_CMD=cloudflared
    goto :START
)

echo [ERROR] cloudflared not found.
pause
exit /b

:START
echo [LAUNCH] Starting tunnel: parrot-backend
%CLOUDFLARE_CMD% tunnel run --url http://localhost:8000 parrot-backend

pause
