import abc


class BaseLLMProvider(abc.ABC):
    """Abstract base for all LLM providers.

    Implementations talk to a concrete backend (local Ollama, a cloud API, …)
    and return the *raw* assistant reply text.  Parsing that text (JSON
    extraction, Traditional-Chinese conversion, artefact stripping, …) is the
    caller's responsibility — providers must not couple themselves to the
    response schema.
    """

    @abc.abstractmethod
    def chat(self, messages: list) -> str:
        """Send *messages* to the model and return the raw reply text.

        *messages* follows the OpenAI chat format
        (``[{"role": ..., "content": ...}, ...]``).
        """
        raise NotImplementedError

    def chat_stream(self, messages: list):
        """Return an async iterator yielding reply text chunks as they arrive.

        Optional: only providers that support token streaming override this.
        The default signals "not supported" so the caller can fall back to the
        blocking ``chat`` path.  Overrides must be ``async def`` generators.
        """
        raise NotImplementedError(
            f"{type(self).__name__} 不支援串流輸出（chat_stream）"
        )
