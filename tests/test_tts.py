import pytest

import backend.services.tts.cache as cache_mod
from backend.services.tts.base import BaseTTSProvider
from backend.services.tts.cache import TTSCache
from backend.services.tts.providers.cloud_provider import CloudTTSProvider


class StubProvider(BaseTTSProvider):
    def __init__(self):
        self.calls = 0

    def synthesize(self, text):
        self.calls += 1
        return b"WAVDATA"


@pytest.fixture
def tmp_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod, "AUDIO_CACHE_DIR", tmp_path)
    return tmp_path


def test_second_call_hits_cache(tmp_cache_dir):
    provider = StubProvider()
    cache = TTSCache(provider)
    first = cache.get_audio("早安主人")
    second = cache.get_audio("早安主人")
    assert first == second == b"WAVDATA"
    # Provider must only be called once; the rest comes from cache.
    assert provider.calls == 1


def test_unimplemented_provider_returns_none(tmp_cache_dir):
    cache = TTSCache(CloudTTSProvider())
    # Skeleton raises NotImplementedError; cache must swallow it to None.
    assert cache.get_audio("你好") is None


def test_empty_text_returns_none(tmp_cache_dir):
    provider = StubProvider()
    cache = TTSCache(provider)
    assert cache.get_audio("") is None
    assert provider.calls == 0
