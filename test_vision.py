import time
import mss
from PIL import Image
import io
from ollama import Client

client = Client(host='http://localhost:11434')

# 🌟 縮小焦點：改為 256x256，減少運算量
def capture_foveated_vision(box_size=256):
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        center_x = monitor["width"] // 2
        center_y = monitor["height"] // 2
        bbox = {
            "top": center_y - box_size // 2,
            "left": center_x - box_size // 2,
            "width": box_size,
            "height": box_size
        }
        sct_img = sct.grab(bbox)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        return img

def test_reaction_speed():
    print("📸 正在擷取螢幕正中央 256x256 畫面...")
    img = capture_foveated_vision()
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_bytes = img_byte_arr.getvalue()

    print("🧠 影像已送出，開始測量大腦反應時間...\n")
    start_time = time.time()
    
    try:
        # 🌟 修改為最直白的問答，不加任何複雜的限制詞
        prompt = "What is the main object in this image? Answer very briefly."
        
        response = client.chat(
            model='llava',
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [img_bytes]
            }]
        )
        
        end_time = time.time()
        latency = end_time - start_time
        result_text = response['message']['content'].strip()
        
        print("="*40)
        print(f"👁️ 視覺關鍵字: {result_text}")
        print(f"⏱️ 總共花費時間: {latency:.2f} 秒")
        print("="*40)
            
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    # 連續測試 3 次，跳過第一次的冷啟動誤差
    for i in range(3):
        print(f"\n--- 測試回合 {i+1} ---")
        test_reaction_speed()
        time.sleep(1) # 稍微喘息一下