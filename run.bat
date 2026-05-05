@echo off
TITLE Parrot AI Studio — Unified Backend & Tunnel
SETLOCAL EnableDelayedExpansion

:: --- CONFIGURATION ---
SET PORT=8000
SET BE_HOST=0.0.0.0
SET TUNNEL_NAME=parrot-backend
SET CLOUDFLARED_PATH="C:\Program Files (x86)\cloudflared\cloudflared.exe"

cls
echo ================================================================
echo   PARROT AI — PROFESSIONAL VOICE STUDIO
echo ================================================================
echo.
echo   [STATUS] Initializing Local GPU Backend...
echo   [STATUS] Initializing Cloudflare Tunnel...
echo.
echo   API URL:    https://parrotai-be.madhur.me
echo   LOCAL:      http://localhost:%PORT%
echo.
echo ================================================================
echo.

:: Check if cloudflared exists
if not exist %CLOUDFLARED_PATH% (
    echo [ERROR] cloudflared.exe not found at %CLOUDFLARED_PATH%
    echo Please check your installation path.
    pause
    exit /b
)

:: 1. Start the Backend in a new window
echo [LAUNCH] Starting FastAPI Backend...
start "Parrot AI: Backend" cmd /k "uvicorn backend.main:app --host %BE_HOST% --port %PORT% --reload"

:: 2. Start the Tunnel in a new window
echo [LAUNCH] Starting Cloudflare Tunnel: %TUNNEL_NAME%...
start "Parrot AI: Tunnel" cmd /k "%CLOUDFLARED_PATH% tunnel --url http://localhost:%PORT% run %TUNNEL_NAME%"

echo.
echo ================================================================
echo   ALL SYSTEMS GO!
echo   Keep this window open to maintain the studio environment.
echo   To stop everything, close the separate Backend and Tunnel windows.
echo ================================================================
echo.

:: Keep main window alive for monitoring
pause
