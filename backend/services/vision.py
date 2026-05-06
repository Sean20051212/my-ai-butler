import io
import random
import threading
import time

import mss
from ollama import Client as OllamaClient
from PIL import Image

from backend.config import OLLAMA_BASE_URL, VISION_MODEL
from backend.models.character import CharacterState

_vision_client = OllamaClient(host=OLLAMA_BASE_URL)

_VISION_PROMPT = (
    "Describe the characters, objects, or narrative actions in this scene. "
    "ABSOLUTELY DO NOT use words like 'screen', 'UI', 'interface', 'website', "
    "'youtube', 'browser', 'screenshot', or 'phone'. "
    "Describe it as if you are looking at a real scene."
)

_BOX_SIZE     = 512
_INTERVAL     = 8   # seconds between captures
_MARGIN_RATIO = 0.15


def start_vision_loop(state: CharacterState) -> None:
    """Spawn the background vision thread.  Writes to *state.latest_vision*."""
    thread = threading.Thread(target=_loop, args=(state,), daemon=True)
    thread.start()


def _loop(state: CharacterState) -> None:
    print("Vision loop started.")
    while True:
        if state.is_chatting:
            time.sleep(1)
            continue
        try:
            img_bytes = _capture_random_region()
            response  = _vision_client.chat(
                model=VISION_MODEL,
                messages=[{
                    "role":    "user",
                    "content": _VISION_PROMPT,
                    "images":  [img_bytes],
                }],
            )
            description = response["message"]["content"].strip()
            state.latest_vision = f"剛剛不經意瞥到了：{description}"
        except Exception as exc:
            print(f"Vision error: {exc}")
        time.sleep(_INTERVAL)


def _capture_random_region() -> bytes:
    with mss.mss() as sct:
        monitor  = sct.monitors[1]
        w, h     = monitor["width"], monitor["height"]
        margin_x = int(w * _MARGIN_RATIO)
        margin_y = int(h * _MARGIN_RATIO)
        max_x    = w - _BOX_SIZE - margin_x
        max_y    = h - _BOX_SIZE - margin_y

        left = random.randint(margin_x, max_x) if max_x > margin_x else w // 2 - _BOX_SIZE // 2
        top  = random.randint(margin_y, max_y) if max_y > margin_y else h // 2 - _BOX_SIZE // 2

        sct_img = sct.grab({"top": top, "left": left, "width": _BOX_SIZE, "height": _BOX_SIZE})
        img     = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()
