import pytest

import backend.services.stt.factory as factory_mod
from backend.services.stt.factory import get_stt_provider
from backend.services.stt.providers.whisper_provider import WhisperSTTProvider


class _FakeSegment:
    def __init__(self, text):
        self.text = text


class _FakeModel:
    """Stands in for faster_whisper.WhisperModel so tests never load a model."""

    def __init__(self):
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append(kwargs)
        # Mimic faster-whisper: (segments_generator, info)
        return iter([_FakeSegment("你好，"), _FakeSegment("主人")]), object()


def test_transcribe_joins_segments():
    provider = WhisperSTTProvider()
    provider._model = _FakeModel()  # skip the real (heavy) model load
    assert provider.transcribe(b"FAKEWAV") == "你好，主人"


def test_empty_audio_skips_model():
    provider = WhisperSTTProvider()
    fake = _FakeModel()
    provider._model = fake
    # Nothing recorded → empty string, and the model must not be touched.
    assert provider.transcribe(b"") == ""
    assert fake.calls == []


def test_language_passed_through():
    provider = WhisperSTTProvider(language="zh")
    fake = _FakeModel()
    provider._model = fake
    provider.transcribe(b"FAKEWAV")
    assert fake.calls[0]["language"] == "zh"


def test_blank_language_means_auto_detect():
    # "" in config should become None (faster-whisper's auto-detect sentinel).
    provider = WhisperSTTProvider(language="")
    fake = _FakeModel()
    provider._model = fake
    provider.transcribe(b"FAKEWAV")
    assert fake.calls[0]["language"] is None


def test_factory_returns_whisper_provider():
    assert isinstance(get_stt_provider(), WhisperSTTProvider)


def test_factory_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr(factory_mod, "STT_PROVIDER", "bogus")
    with pytest.raises(ValueError, match="未知的 STT_PROVIDER"):
        get_stt_provider()
