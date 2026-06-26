import hashlib

from backend.config import AUDIO_CACHE_DIR
from backend.services.tts.base import BaseTTSProvider
from backend.utils.text import preprocess_for_tts

# Ensure cache directory exists at import time.
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class TTSCache:
    """Provider-agnostic, hash-keyed audio cache around any BaseTTSProvider.

    Text is preprocessed once, hashed, and looked up on disk before the
    provider is ever called; identical text always hits the cache on the
    second request.  Any provider can share this wrapper.
    """

    def __init__(self, provider: BaseTTSProvider) -> None:
        self._provider = provider

    def get_audio(self, text: str) -> bytes | None:
        """Return WAV bytes for *text*, hitting the cache before the provider.

        Returns ``None`` when the text collapses to empty after preprocessing,
        the provider is unimplemented, or synthesis otherwise fails — so the
        chat flow continues silently rather than erroring.
        """
        processed = preprocess_for_tts(text)
        if not processed:
            return None

        cache_key  = hashlib.sha256(processed.encode()).hexdigest()[:16]
        cache_path = AUDIO_CACHE_DIR / f"{cache_key}.wav"

        if cache_path.exists():
            print(f"Audio cache hit: {cache_key}.wav")
            return cache_path.read_bytes()

        try:
            audio_bytes = self._provider.synthesize(processed)
        except NotImplementedError:
            # Provider is a skeleton (e.g. cloud vendor not yet wired up).
            return None
        except Exception as exc:
            print(f"TTS error: {exc}")
            return None

        if audio_bytes:
            cache_path.write_bytes(audio_bytes)
        return audio_bytes
