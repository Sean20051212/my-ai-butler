@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === my-ai-butler startup ===
echo.

echo [1/4] Cleaning up old processes on port 8000...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo     Stopping PID %%a
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo [2/4] Checking Ollama (port 11434)...
netstat -ano | findstr ":11434 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% == 0 (
    echo     Ollama already running - skipping.
) else (
    echo     Starting Ollama server...
    start "Ollama" /min cmd /c "ollama serve"
    echo     Waiting for Ollama to come up...
    timeout /t 3 /nobreak >nul
)
echo.

echo [3/4] Starting Backend (FastAPI on 127.0.0.1:8000)...
start "Backend - FastAPI" cmd /k "python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 3 /nobreak >nul

echo [4/4] Starting Frontend (Electron)...
start "Frontend - Electron" cmd /k "npx electron ."

echo.
echo All services started!
echo     Backend:  http://127.0.0.1:8000   (test UI: http://127.0.0.1:8000/docs)
echo     Frontend: Electron window
echo.
echo Note: voice is silent for now (cloud TTS provider not implemented yet);
echo       text chat works as normal.
echo.
pause
