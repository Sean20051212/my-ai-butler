import abc


class BaseSTTProvider(abc.ABC):
    """Abstract base for speech-to-text (voice input) providers.

    Implementations turn a chunk of recorded audio into text.  Callers are
    responsible for assembling microphone frames into a decodable audio
    container before handing it over; a provider only performs the actual
    transcription call.
    """

    @abc.abstractmethod
    def transcribe(self, audio: bytes) -> str:
        """Return the transcript of *audio*.

        *audio* is a complete, decodable audio container (e.g. WAV bytes), not
        raw PCM frames.  Returns an empty string when *audio* is empty or no
        speech is recognised — never ``None`` — so callers can treat "nothing
        was said" uniformly without a null check.
        """
        raise NotImplementedError
