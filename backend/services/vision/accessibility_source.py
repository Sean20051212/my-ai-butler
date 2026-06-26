from backend.services.vision.base import VisionSource
from backend.services.vision.win import get_foreground_window, get_window_title

# Cap how many control labels we gather so the description stays short.
_MAX_TEXTS = 12
_MAX_LABEL_LEN = 30


class AccessibilitySource(VisionSource):
    """Middle layer: read the foreground window's accessibility tree.

    Uses pywinauto to enumerate visible control texts of the active window and
    condenses them into a short description.  Returns ``None`` when pywinauto
    is unavailable, no window is focused, or reading fails.
    """

    def capture(self) -> str | None:
        try:
            from pywinauto import Desktop
        except ImportError:
            return None

        hwnd = get_foreground_window()
        if not hwnd:
            return None
        title = get_window_title(hwnd).strip()

        try:
            window = Desktop(backend="uia").window(handle=hwnd)
            labels: list[str] = []
            for ctrl in window.descendants():
                try:
                    text = (ctrl.window_text() or "").strip()
                except Exception:
                    continue
                if text and text not in labels:
                    labels.append(text[:_MAX_LABEL_LEN])
                if len(labels) >= _MAX_TEXTS:
                    break
        except Exception:
            return None

        if not title and not labels:
            return None
        summary = "、".join(labels) if labels else "（沒有可讀的文字內容）"
        return f"目前在「{title}」這個視窗，畫面上有：{summary}"
