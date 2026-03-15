#!/bin/bash

echo "正在啟動後端伺服器 (FastAPI)..."
# 啟動虛擬環境並在背景執行 FastAPI
source venv/bin/activate
uvicorn server:app --reload &
BACKEND_PID=$!

# 等待 2 秒確保後端啟動
sleep 2

echo "正在啟動前端介面 (Electron)..."
# 在前景執行 Electron
npx electron main.js

# 當關閉 Electron 視窗時，自動清理背景的 FastAPI 伺服器程序
echo "前端已關閉，正在自動關閉後端伺服器..."
kill $BACKEND_PID
echo "已安全關閉所有程序。"
