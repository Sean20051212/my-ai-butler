@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === my-ai-butler startup ===
echo.

echo [1/5] Cleaning up old processes on port 8000...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo     Stopping PID %%a
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo [2/5] Checking GPT-SoVITS TTS (port 9880)...
netstat -ano | findstr ":9880 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% == 0 (
    echo     TTS already running - skipping.
) else (
    echo     Starting GPT-SoVITS API server...
    start "TTS - GPT-SoVITS API" /d "C:\GPT-SoVITS-v3lora-20250228\GPT-SoVITS-v3lora-20250228" cmd /k "runtime\python.exe api_v2.py -a 127.0.0.1 -p 9880"
    echo     GPT-SoVITS is loading models in background, may take 30-60s.
)
echo.

echo [3/5] Starting Backend (FastAPI on 127.0.0.1:8000)...
start "Backend - FastAPI" cmd /k "python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 3 /nobreak >nul

echo [4/5] Starting Frontend (Electron)...
start "Frontend - Electron" cmd /k "npx electron ."

echo.
echo [5/5] All services started!
echo     Backend:  http://127.0.0.1:8000
echo     TTS API:  http://127.0.0.1:9880  wait ~60s for model loading
echo     Frontend: Electron window
echo.
echo If voice is missing, wait for GPT-SoVITS to finish loading then retry.
pause