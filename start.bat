@echo off
:: remove chcp 65001 since it can cause issues parsing batch files saved in certain encodings

echo Starting Backend Server (FastAPI)...
start "Backend - FastAPI" cmd /k "call venv\Scripts\activate && uvicorn server:app --reload"

:: Wait for 2 seconds
timeout /t 2 /nobreak >nul

echo Starting Frontend Interface (Electron)...
start "Frontend - Electron" cmd /k "npx electron main.js"

echo Startup commands sent! You will see two new cmd windows.
pause
