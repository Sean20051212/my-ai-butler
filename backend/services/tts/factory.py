from backend.config import TTS_PROVIDER
from backend.services.tts.base import BaseTTSProvider
from backend.services.tts.providers.cloud_provider import CloudTTSProvider

# Registry of known TTS providers, keyed by the TTS_PROVIDER env value.
_PROVIDERS: dict[str, type[BaseTTSProvider]] = {
    "cloud": CloudTTSProvider,
}


def get_tts_provider() -> BaseTTSProvider:
    """Return the TTS provider instance selected by the TTS_PROVIDER env var.

    Raises a clear error (never fails silently) when the configured value is
    not a known provider.
    """
    provider_cls = _PROVIDERS.get(TTS_PROVIDER)
    if provider_cls is None:
        available = ", ".join(sorted(_PROVIDERS))
        raise ValueError(
            f"未知的 TTS_PROVIDER：'{TTS_PROVIDER}'。可用選項：{available}"
        )
    return provider_cls()
