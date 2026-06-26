from backend.services.tts.base import BaseTTSProvider


class CloudTTSProvider(BaseTTSProvider):
    """Skeleton for a cloud voice-cloning TTS backend.

    The local GPT-SoVITS path has been retired in favour of a hosted service;
    the vendor is not yet decided.  Candidates that support voice cloning and
    multilingual output:
        - ElevenLabs   (https://elevenlabs.io)
        - Azure Speech (Custom Neural Voice)
        - PlayHT       (https://play.ht)

    When chosen, read the API key from config/env (placeholders already noted
    in .env.example, marked DISABLED), call the vendor here, and return audio
    bytes.  Until then this raises NotImplementedError, which the cache layer
    catches and turns into None so the chat flow keeps working without audio.
    """

    def synthesize(self, text: str) -> bytes | None:
        raise NotImplementedError(
            "雲端 TTS provider 尚未實作，待後續決定要接哪家服務"
        )
