@echo off
TITLE Parrot AI Studio — Full Environment Auto-Installer
SETLOCAL EnableDelayedExpansion

echo ================================================================
echo   PARROT AI — AUTO-INSTALLER & MIGRATOR
echo ================================================================
echo.

:: 1. Check for Python/Conda
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ACTION] Python not found. Attempting to install Miniconda...
    
    :: Download Miniconda using curl
    echo [DOWNLOAD] Fetching Miniconda installer...
    curl -L https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe -o miniconda_installer.exe
    
    echo [INSTALL] Installing Miniconda silently (this may take a minute)...
    start /wait "" miniconda_installer.exe /S /D=%UserProfile%\Miniconda3
    
    :: Add to path for this session
    set "PATH=%UserProfile%\Miniconda3;%UserProfile%\Miniconda3\Scripts;%UserProfile%\Miniconda3\Library\bin;%PATH%"
    
    del miniconda_installer.exe
    echo [OK] Miniconda installed.
) else (
    echo [OK] Python detected.
)

:: 2. Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ACTION] Node.js not found. Downloading installer...
    curl -L https://nodejs.org/dist/v20.11.1/node-v20.11.1-x64.msi -o node_installer.msi
    echo [INSTALL] Please follow the Node.js installer prompts...
    start /wait node_installer.msi
    del node_installer.msi
    echo [IMPORTANT] Please RESTART this script after Node.js finishes installing.
    pause
    exit /b
)
echo [OK] Node.js detected.

:: 3. GPU Detection
nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] NVIDIA Drivers not found. 
    echo           Please install drivers from: https://www.nvidia.com/Download/index.aspx
    echo           The backend will fall back to CPU.
    pause
) else (
    echo [OK] NVIDIA GPU detected!
)

:: 4. Install Dependencies
echo.
echo [STEP 1/3] Installing Frontend Dependencies...
call npm install

echo.
echo [STEP 2/3] Installing AI Engine (PyTorch + CUDA 12.1)...
:: This command installs the CUDA binaries automatically
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r backend/requirements.txt

:: 5. Cloudflare Setup
echo.
echo [STEP 3/3] Setting up Cloudflare...
if not exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" (
    echo [DOWNLOAD] Fetching Cloudflare Tunnel installer...
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.msi -o cloudflared.msi
    start /wait cloudflared.msi
    del cloudflared.msi
)

echo [ACTION] Opening Cloudflare Login...
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel login

echo.
echo ================================================================
echo   SETUP FINISHED!
echo   1. Copy your .env files manually.
echo   2. Run run.bat to start.
echo ================================================================
pause
