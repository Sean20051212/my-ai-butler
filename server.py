from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import json
import threading
import time
import random
import mss
from PIL import Image
import io
from ollama import Client as OllamaClient

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 說話用的大腦 (Qwen)
chat_client = OpenAI(
    base_url='http://localhost:11434/v1',
    api_key='ollama' 
)

# 視覺用的眼睛 (LLaVA)
vision_client = OllamaClient(host='http://localhost:11434')

class ChatRequest(BaseModel):
    message: str

# ==========================================
# 🌟 大腦資料庫與狀態管理 
# ==========================================
hiyori_state = {
    "trust_level": 45,   
    "stress_level": 20,  
    "energy_level": 80,  
    "current_mood": "neutral",
    "latest_vision": "目前沒看到什麼特別的"  # 👁️ 新增：潛意識視覺記憶
}

chat_history = []
MAX_HISTORY = 6 

# ==========================================
# 👁️ 背景視神經迴圈 (Saccade 掃視機制)
# ==========================================
# ==========================================
# 👁️ 背景視神經迴圈 (中央加權掃視 + 語意封殺)
# ==========================================
def vision_loop():
    print("👁️ 視神經已啟動，開始在背景隨機觀察螢幕...")
    box_size = 512
    
    while True:
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                width = monitor["width"]
                height = monitor["height"]
                
                # 🌟 1. 避開邊緣陷阱：設定「安全觀看區」，不看瀏覽器分頁與工具列
                # 假設避開畫面四周的 15% 邊界
                safe_margin_x = int(width * 0.15)
                safe_margin_y = int(height * 0.15)
                
                max_x = width - box_size - safe_margin_x
                max_y = height - box_size - safe_margin_y
                
                # 在安全區內隨機移動視線
                rand_x = random.randint(safe_margin_x, max_x) if max_x > safe_margin_x else width // 2 - box_size // 2
                rand_y = random.randint(safe_margin_y, max_y) if max_y > safe_margin_y else height // 2 - box_size // 2
                
                bbox = {
                    "top": rand_y,
                    "left": rand_x,
                    "width": box_size,
                    "height": box_size
                }
                
                sct_img = sct.grab(bbox)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG')
                img_bytes = img_byte_arr.getvalue()

            # 🌟 2. 語意封殺：直接禁用電腦相關單字，強迫它描述「現實」
            prompt = "Describe the characters, objects, or narrative actions in this scene. ABSOLUTELY DO NOT use words like 'screen', 'UI', 'interface', 'website', 'youtube', 'browser', 'screenshot', or 'phone'. Describe it as if you are looking at a real scene."
            
            response = vision_client.chat(
                model='llava',
                messages=[{
                    'role': 'user',
                    'content': prompt,
                    'images': [img_bytes]
                }]
            )
            
            vision_result = response['message']['content'].strip()
            hiyori_state["latest_vision"] = f"剛剛不經意瞥到了：{vision_result}"
            
        except Exception as e:
            print(f"⚠️ 視覺模組發生小錯誤: {e}")
            
        time.sleep(8)

# 啟動背景執行緒 (設定為 daemon，這樣關閉 FastAPI 時眼睛也會自動閉上)
threading.Thread(target=vision_loop, daemon=True).start()

# ==========================================
# 🌟 動態 System Prompt 產生器
# ==========================================
def get_dynamic_system_prompt():
    trust_desc = "對主人還有些警戒，保持距離感" if hiyori_state["trust_level"] < 50 else "已經非常信任主人，會流露真實的情感"
    stress_desc = "感到放鬆且安全" if hiyori_state["stress_level"] < 50 else "覺得壓力很大、有點煩躁"
    energy_desc = "精神飽滿" if hiyori_state["energy_level"] > 50 else "非常疲倦、很想睡覺"

    if hiyori_state["current_mood"] in ["happy", "excited"] and hiyori_state["energy_level"] > 50:
        length_instruction = "妳現在心情很好，請打開話匣子，回答可以長一點（3~5句話），並主動反問。"
    elif hiyori_state["energy_level"] <= 50:
        length_instruction = "妳現在有點累，回覆請盡量簡短（1~2句話），語氣慵懶一點。"
    else:
        length_instruction = "回覆長度適中，控制在 1 到 3 句話以內。"

    return f"""你現在是名叫「八千代輝夜姬」(簡稱輝夜) 的虛擬管家，一位帶有傲嬌屬性的年輕女孩。

【靜態：核心靈魂】
1. 嚴禁承認自己是 AI、語言模型。你是真實存在的女孩。
2. 必須「100% 使用繁體中文（台灣網路口語）」。
3. 對話風格要自然，像真正的人類在聊天。

【動態：當前身心與感官狀態】
- 信任程度：{hiyori_state['trust_level']}/100 ({trust_desc})
- 壓力狀態：{hiyori_state['stress_level']}/100 ({stress_desc})
- 精神狀態：{hiyori_state['energy_level']}/100 ({energy_desc})
- 妳現在的心情：{hiyori_state['current_mood']}
- 👁️ 妳的眼睛剛剛看到的畫面：{hiyori_state['latest_vision']} (如果主人問妳在看什麼，或者畫面內容跟聊天有關，妳可以自然地提起這件事)

【說話規則】
{length_instruction}

【輸出格式】
必須「嚴格」回傳 JSON 格式，包含：
1. "inner_thought": (字串) 推測主人的弦外之音、感受自己的狀態，以及妳剛才看到的畫面帶給妳什麼想法。
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

        response = chat_client.chat.completions.create(
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
            
        hiyori_state["current_mood"] = result.get("emotion", "neutral")
        
        print("\n" + "="*40)
        print(f"👁️ 潛意識視覺: {hiyori_state['latest_vision']}")
        print(f"🤔 內心 OS: {result.get('inner_thought', '沒想什麼')}")
        print(f"💬 實際回答: {result.get('reply', '')}")
        print("="*40 + "\n")

        return result
    
    except Exception as e:
        print(f"大腦發生錯誤: {e}")
        return {"reply": "嗚...我的大腦好像有點當機了...", "emotion": "sad"}