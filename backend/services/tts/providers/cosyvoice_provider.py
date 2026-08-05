import opencc
import requests

from backend.config import COSYVOICE_TTS_URL
from backend.services.tts.base import BaseTTSProvider

# The reply text reaching TTS is Taiwan Traditional (chat.py runs s2twp), but the
# fine-tuned CosyVoice2 model was trained on Simplified Chinese, so convert back
# before synthesis.  tw2sp is the inverse of s2twp (phrase-aware).
_to_simplified = opencc.OpenCC("tw2sp")


class CosyVoiceTTSProvider(BaseTTSProvider):
    """Calls the WSL-hosted CosyVoice2 fukalos inference server over HTTP.

    The heavy model lives in the WSL ``cosyvoice`` conda env behind a small
    ``http.server`` (see ``tts_service/butler_tts_server.py``); this provider
    only converts text to Simplified Chinese and forwards it.  Any failure
    (server down, timeout, non-200) returns ``None`` so the cache layer keeps
    the chat flow going silently instead of raising.
    """

    def __init__(self, url: str = COSYVOICE_TTS_URL, timeout: float = 120.0) -> None:
        self._url = url
        self._timeout = timeout

    def synthesize(self, text: str) -> bytes | None:
        simplified = _to_simplified.convert(text)
        try:
            resp = requests.post(
                self._url, json={"text": simplified}, timeout=self._timeout
            )
        except requests.RequestException as exc:
            print(f"CosyVoice TTS 連線失敗（WSL 服務未啟動？）：{exc}")
            return None

        if resp.status_code == 204:
            # Empty text or no audio produced — silence, not an error.
            return None
        if resp.status_code != 200:
            print(f"CosyVoice TTS 回應異常 {resp.status_code}：{resp.text[:200]}")
            return None
        return resp.content
