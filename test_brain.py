import requests
import time

# 這是你 FastAPI 伺服器的位址
url = "http://127.0.0.1:8000/chat"
data = {"message": "早安！你今天覺得怎麼樣？"}

print("正在傳送訊息給 Hiyori 的大腦 (Ollama)...")
start_time = time.time()

try:
    # 發送 POST 請求
    response = requests.post(url, json=data)
    result = response.json()
    end_time = time.time()
    
    print(f"✅ 思考完成！推論耗時: {end_time - start_time:.2f} 秒")
    print("-" * 30)
    print(f"💬 回覆: {result.get('reply')}")
    print(f"🎭 情緒: {result.get('emotion')}")
    print("-" * 30)
except Exception as e:
    print(f"❌ 連線失敗，請確認 FastAPI 伺服器是否已啟動: {e}")