@echo off
TITLE Parrot AI Studio — Migration & Setup
SETLOCAL EnableDelayedExpansion

echo ================================================================
echo   PARROT AI — ENVIRONMENT MIGRATOR
echo ================================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+ from python.org
    pause
    exit /b
)
echo [OK] Python detected.

:: 2. Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js from nodejs.org
    pause
    exit /b
)
echo [OK] Node.js detected.

:: 3. GPU Detection
nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] No NVIDIA GPU detected or drivers not installed.
    echo           The backend will run on CPU (Slow).
) else (
    echo [OK] NVIDIA GPU detected!
)

:: 4. Install Dependencies
echo.
echo [STEP 1/4] Installing Frontend Dependencies...
call npm install

echo.
echo [STEP 2/4] Installing Backend Dependencies (with CUDA support)...
:: We install the official PyTorch CUDA 11.8/12.1 versions
python -m pip install --upgrade pip
pip install torch torchvision audio --index-url https://download.pytorch.org/whl/cu121
pip install -r backend/requirements.txt

:: 5. Cloudflare Setup
echo.
echo [STEP 3/4] Setting up Cloudflare Tunnel...
if not exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" (
    echo [ACTION] Please download cloudflared from:
    echo          https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.msi
    echo.
    echo Once installed, press any key to continue login...
    pause
)

echo [ACTION] Opening Cloudflare Login...
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel login

:: 6. Environment Variables Reminder
echo.
echo [STEP 4/4] Final Check...
if not exist ".env.local" (
    echo [WARNING] .env.local missing! Please copy it from your old machine.
)
if not exist "backend\.env" (
    echo [WARNING] backend\.env missing! Please copy it from your old machine.
)

echo.
echo ================================================================
echo   SETUP COMPLETE!
echo ================================================================
echo.
echo   To start the studio, just run: run.bat
echo.
pause
