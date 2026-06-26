from backend.config import VISION_CDP_URL
from backend.services.vision.base import VisionSource

# How much visible text to sample from the active page before summarising.
_MAX_TEXT_CHARS = 400


class DomSource(VisionSource):
    """Highest-priority layer: read the active browser tab's DOM directly.

    Requires the user's browser to be running with a CDP endpoint exposed
    (e.g. Chrome launched with ``--remote-debugging-port=9222``).  When
    Playwright is missing, no browser is reachable, or anything goes wrong,
    returns ``None`` so the chain falls through to the next source.
    """

    def capture(self) -> str | None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None

        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(VISION_CDP_URL)
                try:
                    page = self._active_page(browser)
                    if page is None:
                        return None
                    title = (page.title() or "").strip()
                    body = page.inner_text("body") or ""
                finally:
                    browser.close()
        except Exception:
            return None

        snippet = " ".join(body.split())[:_MAX_TEXT_CHARS].strip()
        if not title and not snippet:
            return None
        return f"瀏覽器頁面「{title}」，內容大致是：{snippet}"

    @staticmethod
    def _active_page(browser):
        """Best-effort pick of the most relevant open page."""
        for context in browser.contexts:
            for page in context.pages:
                if not page.is_closed():
                    return page
        return None
