"""Active-window helpers via ctypes/user32.

Kept dependency-free (no pywin32) so the vision layer works on a stock
Windows Python.  Every function degrades to ``None`` off-Windows or on error.
"""
import ctypes
import sys

try:
    import ctypes.wintypes  # noqa: F401  (populates ctypes.wintypes.RECT)
except Exception:
    pass


def _user32():
    if sys.platform != "win32":
        return None
    try:
        return ctypes.windll.user32
    except Exception:
        return None


def get_foreground_window() -> int | None:
    """Return the handle (HWND) of the current foreground window, or None."""
    user32 = _user32()
    if user32 is None:
        return None
    try:
        hwnd = user32.GetForegroundWindow()
        return hwnd or None
    except Exception:
        return None


def get_window_title(hwnd: int) -> str:
    """Return the title text of *hwnd* (empty string on failure)."""
    user32 = _user32()
    if user32 is None or not hwnd:
        return ""
    try:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Return (left, top, right, bottom) of *hwnd*, or None on failure."""
    user32 = _user32()
    if user32 is None or not hwnd:
        return None
    try:
        rect = ctypes.wintypes.RECT()  # type: ignore[attr-defined]
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        pass
    return None
