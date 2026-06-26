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
