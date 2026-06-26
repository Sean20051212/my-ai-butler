import abc


class BaseTTSProvider(abc.ABC):
    """Abstract base for text-to-speech providers.

    Implementations turn already-cleaned text into WAV/audio bytes.  Caching
    and text preprocessing live outside the provider (see ``cache.py``), so a
    provider only needs to perform the actual synthesis call.
    """

    @abc.abstractmethod
    def synthesize(self, text: str) -> bytes | None:
        """Return audio bytes for *text*, or ``None`` when synthesis fails."""
        raise NotImplementedError
