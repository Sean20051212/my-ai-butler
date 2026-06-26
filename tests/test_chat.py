import json

import pytest
from fastapi.testclient import TestClient

import backend.routes.chat as chat_mod
from backend.app import app


@pytest.fixture
def client(monkeypatch):
    # Keep the test hermetic: no real screenshots, no real audio synthesis.
    monkeypatch.setattr(chat_mod.vision_chain, "capture", lambda: None)
    monkeypatch.setattr(chat_mod.tts_cache, "get_audio", lambda text: None)
    with TestClient(app) as c:
        yield c


def test_chat_returns_reply(client, monkeypatch):
    monkeypatch.setattr(
        chat_mod.llm_provider,
        "chat",
        lambda messages: json.dumps(
            {"reply": "哈囉主人", "emotion": "happy", "inner_thought": "開心"}
        ),
    )
    resp = client.post("/chat", json={"message": "早安"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "哈囉主人"


def test_chat_malformed_json_falls_back(client, monkeypatch):
    # LLM returns something that is not valid JSON.
    monkeypatch.setattr(
        chat_mod.llm_provider, "chat", lambda messages: "這不是 JSON"
    )
    resp = client.post("/chat", json={"message": "早安"})
    assert resp.status_code == 200
    body = resp.json()
    # Should degrade to the fallback reply rather than erroring out.
    assert "reply" in body and body["reply"]
