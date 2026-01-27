@echo off
title Parrot AI - Voice Cloning

echo ================================================
echo   Parrot AI - Voice Cloning
echo   Powered by Qwen3-TTS
echo ================================================
echo.

:: Add SoX to PATH
set PATH=%PATH%;C:\Program Files\sox-14.4.2

:: Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo.
    echo Please create it first:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [OK] Virtual environment found
echo [OK] SoX path configured
echo.

:: Run the FastAPI Backend
.venv\Scripts\python.exe -m uvicorn backend:app --host 0.0.0.0 --port 8000 --reload

pause

:: Run the backend 
.\run.bat
:: Run the Next.js Frontend
npm run dev

