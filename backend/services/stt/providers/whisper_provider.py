import io

from backend.config import (
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_LANGUAGE,
    WHISPER_MODEL_SIZE,
)
from backend.services.stt.base import BaseSTTProvider


class WhisperSTTProvider(BaseSTTProvider):
    """Local speech-to-text via faster-whisper (CTranslate2 backend).

    Runs entirely offline.  By default it loads the *small* model in int8 on
    the CPU: this keeps it off the GPU, which is already tight (CosyVoice2 +
    Ollama leave little VRAM headroom), at the cost of a few seconds of latency
    per short utterance.

    ``faster_whisper`` is an optional dependency (see requirements-optional.txt).
    It is imported lazily on first use so the app — and the test suite — keep
    working without it installed; voice input simply stays unavailable until it
    is present, while text chat is unaffected.
    """

    def __init__(
        self,
        model_size: str = WHISPER_MODEL_SIZE,
        device: str = WHISPER_DEVICE,
        compute_type: str = WHISPER_COMPUTE_TYPE,
        language: str = WHISPER_LANGUAGE,
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        # "" means auto-detect; default is "zh" (Chinese-primary butler).
        self._language = language or None
        self._model = None  # lazily loaded on first transcribe()

    def _get_model(self):
        if self._model is None:
            # Heavy, optional import — kept out of module import so a missing
            # dependency only surfaces when voice input is actually used.
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
        return self._model

    def transcribe(self, audio: bytes) -> str:
        if not audio:
            return ""

        segments, _info = self._get_model().transcribe(
            io.BytesIO(audio),
            language=self._language,
            beam_size=5,
        )
        # segments is a generator; joining consumes it and runs the decode.
        return "".join(segment.text for segment in segments).strip()
