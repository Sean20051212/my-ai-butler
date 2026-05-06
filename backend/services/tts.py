import hashlib
import urllib.parse

import requests

from backend.config import (
    AUDIO_CACHE_DIR,
    TTS_API_URL,
    TTS_PROMPT_LANG,
    TTS_PROMPT_TEXT,
    TTS_REF_AUDIO_PATH,
)
from backend.utils.text import preprocess_for_tts

# Ensure cache directory exists at import time
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_audio(text: str) -> bytes | None:
    """Return WAV bytes for *text*, hitting the cache before calling GPT-SoVITS.

    Returns None when TTS is unavailable or the text collapses to empty after
    preprocessing.
    """
    processed = preprocess_for_tts(text)
    if not processed:
        return None

    cache_key  = hashlib.sha256(processed.encode()).hexdigest()[:16]
    cache_path = AUDIO_CACHE_DIR / f"{cache_key}.wav"

    if cache_path.exists():
        print(f"Audio cache hit: {cache_key}.wav")
        return cache_path.read_bytes()

    audio_bytes = _call_gptsovits(processed)
    if audio_bytes:
        cache_path.write_bytes(audio_bytes)
    return audio_bytes


def _call_gptsovits(text: str) -> bytes | None:
    """Call the GPT-SoVITS HTTP API and return raw WAV bytes, or None on error."""
    print(f"Synthesising: {text}")
    url = (
        f"{TTS_API_URL}/tts"
        f"?text={urllib.parse.quote(text)}"
        f"&text_lang=auto"
        f"&ref_audio_path={urllib.parse.quote(TTS_REF_AUDIO_PATH)}"
        f"&prompt_text={urllib.parse.quote(TTS_PROMPT_TEXT)}"
        f"&prompt_lang={TTS_PROMPT_LANG}"
        f"&text_split_method=cut2"
        f"&temperature=0.5"
        f"&top_k=10"
        f"&top_p=0.5"
    )
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            print(f"TTS ok ({len(response.content) // 1024} KB)")
            return response.content
        print(f"TTS error: HTTP {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("TTS offline (port 9880) — start GPT-SoVITS first")
    except Exception as exc:
        print(f"TTS exception: {exc}")
    return None
