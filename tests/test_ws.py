import asyncio

import pytest
from fastapi.testclient import TestClient

import backend.routes.ws as ws_mod
from backend.app import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_ws_text_turn(client, monkeypatch):
    async def fake_run_turn(message, state, memory):
        assert message == "早安"
        return {"reply": "哈囉主人", "emotion": "happy", "audio_base64": "QUJD"}

    monkeypatch.setattr(ws_mod, "run_turn", fake_run_turn)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "text", "text": "早安"})

        reply = ws.receive_json()
        assert reply["type"] == "reply"
        assert reply["text"] == "哈囉主人"
        assert reply["emotion"] == "happy"

        audio = ws.receive_json()
        assert audio["type"] == "audio"
        assert audio["seq"] == 0
        assert audio["base64"] == "QUJD"

        end = ws.receive_json()
        assert end["type"] == "turn_end"


def test_ws_no_audio_when_tts_silent(client, monkeypatch):
    async def fake_run_turn(message, state, memory):
        return {"reply": "沒有聲音", "emotion": "neutral"}  # no audio_base64

    monkeypatch.setattr(ws_mod, "run_turn", fake_run_turn)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "text", "text": "測試"})
        assert ws.receive_json()["type"] == "reply"
        # Straight to turn_end — no audio segment when synthesis is silent.
        assert ws.receive_json()["type"] == "turn_end"


def test_ws_blank_text_ignored(client, monkeypatch):
    async def fake_run_turn(message, state, memory):
        return {"reply": "有回覆", "emotion": "neutral"}

    monkeypatch.setattr(ws_mod, "run_turn", fake_run_turn)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "text", "text": "   "})  # whitespace only → ignored
        ws.send_json({"type": "text", "text": "真的訊息"})
        # First real output belongs to the second (non-blank) message.
        assert ws.receive_json()["type"] == "reply"


def test_ws_audio_transcribes_then_runs_turn(client, monkeypatch):
    monkeypatch.setattr(ws_mod.stt_provider, "transcribe", lambda audio: "今天天氣如何")

    async def fake_run_turn(message, state, memory):
        assert message == "今天天氣如何"  # the transcript drives the turn
        return {"reply": "很好喔", "emotion": "happy"}

    monkeypatch.setattr(ws_mod, "run_turn", fake_run_turn)

    with client.websocket_connect("/ws") as ws:
        ws.send_bytes(b"FAKE_WEBM_AUDIO")

        transcript = ws.receive_json()
        assert transcript["type"] == "transcript"
        assert transcript["text"] == "今天天氣如何"

        assert ws.receive_json()["type"] == "reply"
        assert ws.receive_json()["type"] == "turn_end"


def test_ws_silent_audio_no_turn(client, monkeypatch):
    # STT heard nothing → emit an empty transcript and do not start a turn.
    monkeypatch.setattr(ws_mod.stt_provider, "transcribe", lambda audio: "   ")

    async def fake_run_turn(message, state, memory):  # pragma: no cover
        raise AssertionError("run_turn must not run on silent audio")

    monkeypatch.setattr(ws_mod, "run_turn", fake_run_turn)

    with client.websocket_connect("/ws") as ws:
        ws.send_bytes(b"SILENCE")
        transcript = ws.receive_json()
        assert transcript["type"] == "transcript"
        assert transcript["text"] == ""


def test_ws_interrupt_stops_turn(client, monkeypatch):
    async def slow_run_turn(message, state, memory):
        await asyncio.sleep(5)  # long enough to be interrupted mid-flight
        return {"reply": "太慢了", "emotion": "neutral"}

    monkeypatch.setattr(ws_mod, "run_turn", slow_run_turn)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "text", "text": "開始"})
        ws.send_json({"type": "interrupt"})
        stopped = ws.receive_json()
        assert stopped["type"] == "stopped"
