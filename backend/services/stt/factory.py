from backend.config import STT_PROVIDER
from backend.services.stt.base import BaseSTTProvider
from backend.services.stt.providers.whisper_provider import WhisperSTTProvider

# Registry of known STT providers, keyed by the STT_PROVIDER env value.
_PROVIDERS: dict[str, type[BaseSTTProvider]] = {
    "whisper": WhisperSTTProvider,
}


def get_stt_provider() -> BaseSTTProvider:
    """Return the STT provider instance selected by the STT_PROVIDER env var.

    Raises a clear error (never fails silently) when the configured value is
    not a known provider.
    """
    provider_cls = _PROVIDERS.get(STT_PROVIDER)
    if provider_cls is None:
        available = ", ".join(sorted(_PROVIDERS))
        raise ValueError(
            f"未知的 STT_PROVIDER：'{STT_PROVIDER}'。可用選項：{available}"
        )
    return provider_cls()
