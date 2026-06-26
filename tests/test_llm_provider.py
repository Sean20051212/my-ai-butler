import pytest

import backend.services.llm.factory as factory
from backend.services.llm.providers.cloud_provider import CloudLLMProvider
from backend.services.llm.providers.ollama_provider import OllamaProvider


def test_factory_selects_ollama(monkeypatch):
    monkeypatch.setattr(factory, "LLM_PROVIDER", "ollama")
    assert isinstance(factory.get_llm_provider(), OllamaProvider)


def test_factory_selects_cloud(monkeypatch):
    monkeypatch.setattr(factory, "LLM_PROVIDER", "cloud")
    assert isinstance(factory.get_llm_provider(), CloudLLMProvider)


def test_factory_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr(factory, "LLM_PROVIDER", "does-not-exist")
    with pytest.raises(ValueError) as exc:
        factory.get_llm_provider()
    # Error should name the bad value and list valid options, not fail silently.
    assert "does-not-exist" in str(exc.value)


def test_cloud_provider_chat_not_implemented():
    with pytest.raises(NotImplementedError):
        CloudLLMProvider().chat([])
