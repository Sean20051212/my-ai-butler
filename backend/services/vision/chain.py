import time

from backend.config import VISION_CACHE_TTL
from backend.services.vision.accessibility_source import AccessibilitySource
from backend.services.vision.base import VisionSource
from backend.services.vision.dom_source import DomSource
from backend.services.vision.vlm_source import VlmSource
from backend.services.vision.win import get_foreground_window


class VisionChain:
    """Try each perception source in priority order, return the first hit.

    Priority: DOM (structured) → accessibility tree → VLM screenshot (costly,
    last resort).  A short TTL cache keyed on the active window avoids re-running
    the whole fallback chain when the user asks again within a few seconds while
    looking at the same window.
    """

    def __init__(self, sources: list[VisionSource] | None = None, ttl: float = VISION_CACHE_TTL) -> None:
        self._sources = sources if sources is not None else [
            DomSource(),
            AccessibilitySource(),
            VlmSource(),
        ]
        self._ttl = ttl
        self._cache_key: object = None
        self._cache_value: str | None = None
        self._cache_time: float = 0.0

    def capture(self) -> str | None:
        """Return the first available scene description, or None if all fail."""
        key = get_foreground_window()
        now = time.monotonic()
        if (
            self._cache_value is not None
            and key == self._cache_key
            and now - self._cache_time < self._ttl
        ):
            return self._cache_value

        result: str | None = None
        for source in self._sources:
            result = source.capture()
            if result is not None:
                break

        # Cache only successful captures so failures retry promptly.
        if result is not None:
            self._cache_key = key
            self._cache_value = result
            self._cache_time = now
        return result


_chain: VisionChain | None = None


def get_vision_chain() -> VisionChain:
    """Return the process-wide VisionChain singleton."""
    global _chain
    if _chain is None:
        _chain = VisionChain()
    return _chain
