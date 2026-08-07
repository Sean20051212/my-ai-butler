import pytest
from fastapi.testclient import TestClient

import backend.conversation as convo_mod
from backend.app import app


@pytest.fixture
def client(monkeypatch):
    # Keep the test hermetic: no real screenshots, no real audio synthesis.
    monkeypatch.setattr(convo_mod.vision_chain, "capture", lambda: None)
    monkeypatch.setattr(convo_mod.tts_cache, "get_audio", lambda text: None)
    with TestClient(app) as c:
        yield c


def test_chat_returns_reply(client, monkeypatch):
    monkeypatch.setattr(
        convo_mod.llm_provider, "chat", lambda messages: "[happy]哈囉主人"
    )
    resp = client.post("/chat", json={"message": "早安"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "哈囉主人"
    assert body["emotion"] == "happy"


def test_chat_untagged_reply_defaults_neutral(client, monkeypatch):
    # No emotion tag → keep the whole text, default to neutral (not an error).
    monkeypatch.setattr(
        convo_mod.llm_provider, "chat", lambda messages: "沒有標記的一句話"
    )
    resp = client.post("/chat", json={"message": "早安"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "沒有標記的一句話"
    assert body["emotion"] == "neutral"


def test_chat_empty_reply_falls_back(client, monkeypatch):
    # Model produced only a tag / nothing speakable → safe fallback reply.
    monkeypatch.setattr(convo_mod.llm_provider, "chat", lambda messages: "[happy]")
    resp = client.post("/chat", json={"message": "早安"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"]  # non-empty fallback
