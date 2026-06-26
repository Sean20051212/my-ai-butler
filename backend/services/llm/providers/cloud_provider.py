from backend.services.llm.base import BaseLLMProvider


class CloudLLMProvider(BaseLLMProvider):
    """Skeleton for a cloud LLM backend (Claude / Gemini / …).

    Intentionally unimplemented: the project keeps inference local (Ollama)
    for now and reserves this as the extension point for a hosted API.
    """

    def chat(self, messages: list) -> str:
        # TODO: implement once the cloud vendor is decided (Claude / Gemini /
        # OpenAI …).  Wire up the API key from config/env, map *messages* to
        # the vendor's chat format, and return the raw reply text.
        raise NotImplementedError(
            "雲端 provider 尚未實作，待後續決定要接哪家 API"
        )
