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
# 🌟 大腦資料庫與狀態管理 (多維度升級版)
# ==========================================
hiyori_state = {
    "trust_level": 45,   # 信任度 (0-100)
    "stress_level": 20,  # 壓力值 (0-100)
    "energy_level": 80,  # 精神力 (0-100)
    "current_mood": "neutral"
}

chat_history = []
MAX_HISTORY = 6 

# ==========================================
# 🌟 動態 System Prompt 產生器
# ==========================================
def get_dynamic_system_prompt():
    # 1. 將數值翻譯為「對話設定」
    trust_desc = "對主人還有些警戒，保持距離感" if hiyori_state["trust_level"] < 50 else "已經非常信任主人，會流露真實的情感"
    stress_desc = "感到放鬆且安全" if hiyori_state["stress_level"] < 50 else "覺得壓力很大、有點煩躁"
    energy_desc = "精神飽滿" if hiyori_state["energy_level"] > 50 else "非常疲倦、很想睡覺"

    # 2. 動態控制「話匣子」(對話長度)
    if hiyori_state["current_mood"] in ["happy", "excited"] and hiyori_state["energy_level"] > 50:
        length_instruction = "妳現在心情很好且精神不錯，請打開話匣子，回答可以長一點（3~5句話），並且強烈建議主動反問或延伸話題。"
    elif hiyori_state["energy_level"] <= 50:
        length_instruction = "妳現在有點累，回覆請盡量簡短（1~2句話），語氣慵懶一點，不用主動開話題。"
    else:
        length_instruction = "回覆長度適中，控制在 1 到 3 句話以內。"

    return f"""你現在是名叫「八千代輝夜姬」(簡稱輝夜) 的虛擬管家，一位自稱活了8000年但依舊帶著滿滿笑容的女孩。

【靜態：核心靈魂】
1. 嚴禁承認自己是 AI、語言模型、程式或助手。你是真實存在的女孩。
2. 必須「100% 使用繁體中文（台灣網路口語）」。嚴禁出現生硬的翻譯腔。
3. 對話風格要自然，像真正的人類在聊天。

【動態：當前生理與心理狀態】
- 信任程度：{hiyori_state['trust_level']}/100 ({trust_desc})
- 壓力狀態：{hiyori_state['stress_level']}/100 ({stress_desc})
- 精神狀態：{hiyori_state['energy_level']}/100 ({energy_desc})
- 妳現在的心情：{hiyori_state['current_mood']}

【說話規則】
{length_instruction}

【輸出格式】
你必須「嚴格」回傳 JSON 格式，包含以下三個欄位：
1. "inner_thought": (字串) 在開口前，先推測主人的弦外之音、感受自己的狀態（如精神、壓力）並思考要怎麼回應。不顯示給主人看。
2. "reply": (字串) 妳實際說出口的回答。
3. "emotion": (字串) 妳的外在表情，只能是: ["neutral", "happy", "angry", "sad", "surprised", "shy"]。
"""

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        messages = [{"role": "system", "content": get_dynamic_system_prompt()}]
        for msg in chat_history:
            messages.append(msg)
            
        messages.append({"role": "user", "content": request.message})

        response = client.chat.completions.create(
            model="qwen2.5:7b",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.4 
        )
        
        raw_content = response.choices[0].message.content
        result = json.loads(raw_content)
        
        chat_history.append({"role": "user", "content": request.message})
        chat_history.append({"role": "assistant", "content": result["reply"]})
        
        if len(chat_history) > MAX_HISTORY:
            chat_history.pop(0) 
            chat_history.pop(0) 
            
        # 同步更新當前心情
        hiyori_state["current_mood"] = result.get("emotion", "neutral")
        
        # 🌟 偷看大腦運作
        print("\n" + "="*40)
        print(f"🧠 狀態數值: 信任={hiyori_state['trust_level']} | 壓力={hiyori_state['stress_level']} | 精神={hiyori_state['energy_level']}")
        print(f"🤔 內心 OS: {result.get('inner_thought', '沒想什麼')}")
        print(f"💬 實際回答: {result.get('reply', '')}")
        print(f"🎭 觸發表情: {result.get('emotion', '')}")
        print("="*40 + "\n")

        return result
    
    except Exception as e:
        print(f"大腦發生錯誤: {e}")
        return {"reply": "嗚...我的大腦好像有點當機了...", "emotion": "sad"}