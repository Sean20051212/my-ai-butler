import io

import mss
from ollama import Client as OllamaClient
from PIL import Image

from backend.config import OLLAMA_BASE_URL, VISION_MODEL
from backend.services.vision.base import VisionSource
from backend.services.vision.win import get_foreground_window, get_window_rect

_VISION_PROMPT = (
    "Describe the characters, objects, or narrative actions in this scene. "
    "ABSOLUTELY DO NOT use words like 'screen', 'UI', 'interface', 'website', "
    "'youtube', 'browser', 'screenshot', or 'phone'. "
    "Describe it as if you are looking at a real scene."
)


class VlmSource(VisionSource):
    """Last-resort layer: screenshot the active window and caption it with a VLM.

    Captures the foreground window's region (falling back to the primary
    monitor when the window bounds are unavailable) and asks the local llava
    model to describe it.  Returns ``None`` on any failure.
    """

    def __init__(self) -> None:
        self._client = OllamaClient(host=OLLAMA_BASE_URL)

    def capture(self) -> str | None:
        try:
            img_bytes = self._grab_active_window()
            response = self._client.chat(
                model=VISION_MODEL,
                messages=[{
                    "role":    "user",
                    "content": _VISION_PROMPT,
                    "images":  [img_bytes],
                }],
            )
            description = response["message"]["content"].strip()
        except Exception:
            return None

        if not description:
            return None
        return f"剛剛不經意瞥到了：{description}"

    @staticmethod
    def _grab_active_window() -> bytes:
        hwnd = get_foreground_window()
        rect = get_window_rect(hwnd) if hwnd else None

        with mss.mss() as sct:
            if rect:
                left, top, right, bottom = rect
                width, height = right - left, bottom - top
                if width > 0 and height > 0:
                    region = {"top": top, "left": left, "width": width, "height": height}
                else:
                    region = sct.monitors[1]
            else:
                region = sct.monitors[1]

            sct_img = sct.grab(region)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
