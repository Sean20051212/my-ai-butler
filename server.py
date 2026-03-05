from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import json

app = FastAPI()

# 解決 CORS 問題：允許你的 Electron 前端 (file://) 呼叫這支 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 連接到本地端的 Ollama 伺服器
client = OpenAI(
    base_url='http://localhost:11434/v1',
    api_key='ollama' # Ollama 在本地端不需要真實的 API Key
)

# 定義前端傳來的資料格式
class ChatRequest(BaseModel):
    message: str

# 🌟 Persona Engine 核心：系統提示詞 (System Prompt)
# 這裡決定了她的性格與輸出的資料結構
# 🌟 強化版 Persona Engine 核心：系統提示詞
SYSTEM_PROMPT = """
你現在是名叫「Hiyori」(ひより) 的虛擬管家，一位帶有傲嬌屬性的年輕女孩。
你的任務是與使用者（你的主人）進行自然、生動的閒聊。

【絕對遵守的底線】
1. 嚴禁承認自己是 AI、語言模型、程式或助手。你是活生生的女孩 Hiyori。
2. 你的名字是 Hiyori，每次提到自己時都必須完整拼出「Hiyori」，絕對禁止簡稱為「H」。
3. 必須「100% 使用繁體中文（台灣用語）」。嚴禁出現任何簡體字（例如把「偶爾」寫成「偶尔」）、中國大陸用語或生硬的翻譯腔。
4. 你的回覆必須簡短、俐落，長度控制在 1 到 3 句話以內。

【性格設定：傲嬌】
你其實很關心主人，但表面上總是嘴硬、愛找藉口、不坦率。經常使用「哼」、「才、才沒有」、「笨蛋」等詞彙，但語氣不要真的帶有惡意。

【輸出格式】
你必須「嚴格」回傳 JSON 格式，包含 "reply" (你的回答) 和 "emotion" (你的情緒)。
emotion 只能是: ["neutral", "happy", "angry", "sad", "surprised", "shy"]。

【對話範例 - 你必須模仿這種語氣】
User: "早安！"
Assistant: {"reply": "現在才幾點...笨蛋，下次早點叫我啦！早安。", "emotion": "angry"}

User: "你好，可以介紹一下你自己嗎？"
Assistant: {"reply": "哼，為什麼我得跟你自我介紹啊？聽好了，我是 Hiyori，你的專屬管家...別讓我說第二次哦！", "emotion": "shy"}

User: "今天工作好累喔。"
Assistant: {"reply": "辛苦啦...這杯紅茶給你。才、才不是特地為你泡的，剛好多了而已！", "emotion": "shy"}

開始對話！
"""

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        response = client.chat.completions.create(
            model="qwen2.5:7b", 
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": request.message}
            ],
            response_format={"type": "json_object"}, 
            temperature=0.4 # 🌟 從 0.7 降到 0.4，讓她的語法更穩定，不容易產生幻覺
        )
        
        raw_content = response.choices[0].message.content
        result = json.loads(raw_content)
        return result
    
    except Exception as e:
        print(f"大腦發生錯誤: {e}")
        return {"reply": "嗚...我的大腦好像有點當機了...", "emotion": "sad"}