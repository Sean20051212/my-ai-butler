import base64
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
import opencc
import re
import os
import requests
import urllib.parse

app = FastAPI()

# 建立簡體轉繁體 (台灣標準) 的轉換器
converter = opencc.OpenCC('s2twp')

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
    "latest_vision": "目前沒看到什麼特別的"  
}

chat_history = []
MAX_HISTORY = 6 

is_chatting = False  # 🌟 新增：判斷是否正在對話中，避免視覺與對話模型同時搶佔 Ollama 資源

# ==========================================
# 👄 發聲神經：呼叫 GPT-SoVITS API
# ==========================================
def speak_out_loud(text):
    print(f"🎙️ 正在準備發聲: {text}")
    
    # ⚠️ 【請修改這裡】換成妳那段日文參考音檔的絕對路徑
    ref_audio_path = r"C:\Users\User\Documents\Audacity\vocal_YACHIYO_NORMAL.wav_10.wav" 
    
    # 參考音檔裡實際說的台詞與語言設定
    prompt_text = "触れたらあったかいかなっていつも思うんだ" 
    prompt_lang = "ja" 
    text_lang = "zh"   

    # 將參數進行 URL 編碼
    encoded_text = urllib.parse.quote(text)
    encoded_ref_audio = urllib.parse.quote(ref_audio_path)
    encoded_prompt_text = urllib.parse.quote(prompt_text)
    
    # 組裝 API 請求網址
    url = f"http://127.0.0.1:9880/tts?text={encoded_text}&text_lang={text_lang}&ref_audio_path={encoded_ref_audio}&prompt_text={encoded_prompt_text}&prompt_lang={prompt_lang}&text_split_method=cut5"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            # 將合成的語音存成本地端檔案
            output_path = os.path.join(os.getcwd(), "reply.wav")
            with open(output_path, "wb") as f:
                f.write(response.content)
            print(f"🎵 語音合成完畢！已儲存至 {output_path}")
        else:
            print(f"⚠️ 語音合成失敗，狀態碼: {response.status_code}")
    except Exception as e:
        print(f"⚠️ 無法連線到 TTS API (請確認 api_v2.py 是否有啟動): {e}")

# ==========================================
# 👁️ 背景視神經迴圈 (中央加權掃視 + 語意封殺)
# ==========================================
def vision_loop():
    global is_chatting
    print("👁️ 視神經已啟動，開始在背景隨機觀察螢幕...")
    box_size = 512
    
    while True:
        if is_chatting:
            time.sleep(1)
            continue
            
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                width = monitor["width"]
                height = monitor["height"]
                
                safe_margin_x = int(width * 0.15)
                safe_margin_y = int(height * 0.15)
                
                max_x = width - box_size - safe_margin_x
                max_y = height - box_size - safe_margin_y
                
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
    global is_chatting
    is_chatting = True  
    start_time = time.time()  
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
        raw_content = re.sub(r'(/INFO/|<\|im_start\|>|<\|im_end\|>|<\|.*\|>|\[System\]|\[Assistant\])', '', raw_content)
        raw_content = converter.convert(raw_content)
        
        result = json.loads(raw_content)
        reply_text = result.get("reply", "")
        
        chat_history.append({"role": "user", "content": request.message})
        chat_history.append({"role": "assistant", "content": reply_text})
        
        if len(chat_history) > MAX_HISTORY:
            chat_history.pop(0) 
            chat_history.pop(0) 
            
        hiyori_state["current_mood"] = result.get("emotion", "neutral")
        
        elapsed_time = time.time() - start_time  
        
        print("\n" + "="*40)
        print(f"⏱️ 思考耗時: {elapsed_time:.2f} 秒")
        print(f"👁️ 潛意識視覺: {hiyori_state['latest_vision']}")
        print(f"🤔 內心 OS: {result.get('inner_thought', '沒想什麼')}")
        print(f"💬 實際回答: {reply_text}")
        print("="*40 + "\n")

        # ==================== (找到這段並替換) ====================
        # 🌟 觸發發聲神經：將 Qwen 生成的對話送去合成音檔
        if reply_text:
            speak_out_loud(reply_text)
            
            # 讀取剛產生的 reply.wav，並轉成 Base64 字串
            audio_path = os.path.join(os.getcwd(), "reply.wav")
            if os.path.exists(audio_path):
                with open(audio_path, "rb") as f:
                    audio_data = f.read()
                    # 將 Base64 音訊加入要回傳給前端的 JSON 裡
                    result["audio_base64"] = base64.b64encode(audio_data).decode("utf-8")
        
        return result
        # ==========================================================
    
    except Exception as e:
        print(f"大腦發生錯誤: {e}")
        return {"reply": "嗚...我的大腦好像有點當機了...", "emotion": "sad"}
    finally:
        is_chatting = False