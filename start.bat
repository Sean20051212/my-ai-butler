@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === my-ai-butler startup ===
echo.

echo [1/5] Cleaning up old backend on port 8000...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo     Stopping PID %%a
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo [2/5] Checking Ollama (port 11434)...
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

echo [3/5] Starting CosyVoice TTS server in WSL...
for /f "delims=" %%i in ('wsl -d Ubuntu wslpath "%~dp0tts_service\run_tts_server.sh"') do set "TTS_SH=%%i"
start "CosyVoice TTS (WSL)" cmd /k "wsl -d Ubuntu bash %TTS_SH%"
echo     Waiting for CosyVoice model to load (this can take ~30-60s)...
set /a tries=0
:waittts
curl -s -o nul http://localhost:9880/health >nul 2>&1
if %errorlevel% == 0 goto ttsready
set /a tries+=1
if %tries% geq 60 (
    echo     WARNING: TTS server not ready after timeout; continuing without voice.
    echo              Check the "CosyVoice TTS (WSL)" window for errors.
    goto ttsdone
)
timeout /t 3 /nobreak >nul
goto waittts
:ttsready
echo     CosyVoice TTS server is ready.
:ttsdone
echo.

echo [4/5] Starting Backend (FastAPI on 127.0.0.1:8000)...
start "Backend - FastAPI" cmd /k "python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 3 /nobreak >nul

echo [5/5] Starting Frontend (Electron)...
start "Frontend - Electron" cmd /k "npx electron ."

echo.
echo All services started!
echo     Backend:  http://127.0.0.1:8000   (test UI: http://127.0.0.1:8000/docs)
echo     TTS:      http://localhost:9880/health   (CosyVoice fukalos voice, via WSL)
echo     Frontend: Electron window (Furina Live2D)
echo.
pause
