from backend.config import LLM_PROVIDER
from backend.services.llm.base import BaseLLMProvider
from backend.services.llm.providers.cloud_provider import CloudLLMProvider
from backend.services.llm.providers.ollama_provider import OllamaProvider

# Registry of known providers, keyed by the LLM_PROVIDER env value.
_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "ollama": OllamaProvider,
    "cloud":  CloudLLMProvider,
}


def get_llm_provider() -> BaseLLMProvider:
    """Return the LLM provider instance selected by the LLM_PROVIDER env var.

    Raises a clear error (never fails silently) when the configured value is
    not a known provider.
    """
    provider_cls = _PROVIDERS.get(LLM_PROVIDER)
    if provider_cls is None:
        available = ", ".join(sorted(_PROVIDERS))
        raise ValueError(
            f"未知的 LLM_PROVIDER：'{LLM_PROVIDER}'。可用選項：{available}"
        )
    return provider_cls()
