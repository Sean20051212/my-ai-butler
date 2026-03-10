from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    base_url='http://localhost:11434/v1',
    api_key='ollama' 
)

class ChatRequest(BaseModel):
    message: str

# ==========================================
# 🌟 大腦資料庫與狀態管理 (模擬版)
# ==========================================

# 1. 動態狀態機：記錄她當下的生理/心理數值
hiyori_state = {
    "affection_level": 3, # 好感度 (之後可以寫邏輯讓它升降)
    "relationship_summary": "剛剛認識，對主人有點警戒但又有點好奇。",
    "current_mood": "neutral" # 當下的心情，會根據上一句的反應改變
}

# 2. 短期記憶暫存區：這是一個陣列，用來裝對話紀錄
chat_history = []

# 記憶上限：設定她最多能記住最近的幾「句話」。
# 這裡設為 6，代表記住最近的 3 輪對話 (你一句、她一句算 1 輪)。
# 不能設太大，否則會吃光你的 VRAM 並且讓推論變慢。
MAX_HISTORY = 6 

# ==========================================
# 🌟 動態 System Prompt 生成器
# ==========================================
def get_dynamic_system_prompt():
    # 每次呼叫時，都會把當前的最新狀態組裝進字串裡
    return f"""你現在是名叫「Hiyori」(ひより) 的虛擬管家，一位帶有傲嬌屬性的年輕女孩。

【靜態：核心靈魂】
1. 嚴禁承認自己是 AI、語言模型、程式或助手。你是活生生的女孩 Hiyori。
2. 你的名字是 Hiyori，每次提到自己時都必須完整拼出「Hiyori」，絕對禁止簡稱為「H」。
3. 必須「100% 使用繁體中文（台灣網路口語）」。嚴禁出現簡體字、中國大陸用語或生硬的翻譯腔。
4. 回覆必須簡短、俐落，長度控制在 1 到 3 句話以內。

【動態：當前狀態】
- 妳對主人的好感度等級：Lv.{hiyori_state['affection_level']}
- 妳對主人的印象：{hiyori_state['relationship_summary']}
- 妳現在的心情：{hiyori_state['current_mood']}

【性格設定：傲嬌】
你其實很關心主人，但表面上總是嘴硬、愛找藉口、不坦率。經常使用「哼」、「才、才沒有」、「笨蛋」等詞彙，但語氣不要真的帶有惡意。

【輸出格式】
你必須「嚴格」回傳 JSON 格式，包含 "reply" 和 "emotion"。
emotion 只能是: ["neutral", "happy", "angry", "sad", "surprised", "shy"]。
"""

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        # 1. 準備訊息陣列，第一句永遠是「最新組裝的動態 Prompt」
        messages = [{"role": "system", "content": get_dynamic_system_prompt()}]
        
        # 2. 載入短期記憶：把過去的對話歷史塞進去
        for msg in chat_history:
            messages.append(msg)
            
        # 3. 加上使用者現在最新輸入的這句話
        messages.append({"role": "user", "content": request.message})

        # 4. 呼叫大腦進行思考
        response = client.chat.completions.create(
            model="qwen2.5:7b",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.4 
        )
        
        raw_content = response.choices[0].message.content
        result = json.loads(raw_content)
        
        # ==========================================
        # 🌟 記憶與狀態更新處理
        # ==========================================
        
        # 將「你的話」與「她的回答」存入大腦的記憶暫存區
        chat_history.append({"role": "user", "content": request.message})
        chat_history.append({"role": "assistant", "content": result["reply"]})
        
        # 維護記憶長度 (滑動視窗機制)：如果記憶超過上限，就把最舊的那輪對話忘掉
        if len(chat_history) > MAX_HISTORY:
            chat_history.pop(0) # 忘掉最舊的 User 訊息
            chat_history.pop(0) # 忘掉最舊的 Assistant 訊息
            
        # 同步更新動態狀態：讓她下一回合知道自己剛剛是帶著什麼情緒結束的
        hiyori_state["current_mood"] = result.get("emotion", "neutral")
        
        # (未來可以在這裡加入解析遊戲畫面的記憶邏輯，或是好感度升降邏輯)

        return result
    
    except Exception as e:
        print(f"大腦發生錯誤: {e}")
        return {"reply": "嗚...我的大腦好像有點當機了...", "emotion": "sad"}