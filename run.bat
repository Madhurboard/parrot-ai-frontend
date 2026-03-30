@echo off
title Parrot AI - Voice Cloning
color 0A

echo ================================================
echo   Parrot AI - Voice Cloning
echo   Powered by Qwen3-TTS  (Supabase Edition)
echo ================================================
echo.

:: Add SoX to PATH
set PATH=%PATH%;C:\Program Files\sox-14.4.2

:: Activate conda environment
call conda activate gpu

echo [OK] Environment activated
echo [OK] SoX path configured
echo.

:: Run the Supabase-integrated FastAPI Backend
echo [LAUNCH] Starting backend.main:app ...
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

pause
