@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === my-ai-butler 啟動程序 ===
echo.

:: 清理舊的 server 進程（port 8000）
echo [1/4] 清理舊進程...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo     停止 PID %%a
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: 檢查 GPT-SoVITS 是否在線
echo [2/4] 檢查 GPT-SoVITS TTS (port 9880)...
netstat -ano | findstr ":9880 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% == 0 (
    echo     TTS 在線，語音功能正常。
) else (
    echo     [警告] TTS 離線！請先啟動 GPT-SoVITS，否則無語音輸出。
)
echo.

:: 啟動 FastAPI 後端
echo [3/4] 啟動 Backend (FastAPI on 127.0.0.1:8000)...
start "Backend - FastAPI" cmd /k "python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload"

:: 等後端起來
timeout /t 3 /nobreak >nul

:: 啟動 Electron 前端
echo [4/4] 啟動 Frontend (Electron)...
start "Frontend - Electron" cmd /k "npx electron ."

echo.
echo 啟動完成！請查看兩個新視窗。
pause
