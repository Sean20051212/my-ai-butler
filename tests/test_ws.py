import asyncio

import pytest
from fastapi.testclient import TestClient

import backend.routes.ws as ws_mod
from backend.app import app


class _DummyQueue:
    def cancel_all(self):
        pass


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_ws_text_turn(client, monkeypatch):
    async def fake_stream(message, state, memory, emit, register_queue=None):
        assert message == "早安"
        if register_queue:
            register_queue(_DummyQueue())
        await emit({"type": "emotion", "emotion": "happy"})
        await emit({"type": "reply_chunk", "text": "哈囉主人"})
        await emit({"type": "audio", "seq": 0, "base64": "QUJD"})
        await emit({"type": "turn_end"})

    monkeypatch.setattr(ws_mod, "run_turn_streaming", fake_stream)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "text", "text": "早安"})

        assert ws.receive_json() == {"type": "emotion", "emotion": "happy"}
        assert ws.receive_json() == {"type": "reply_chunk", "text": "哈囉主人"}
        audio = ws.receive_json()
        assert audio["type"] == "audio" and audio["seq"] == 0
        assert ws.receive_json()["type"] == "turn_end"


def test_ws_audio_transcribes_then_runs_turn(client, monkeypatch):
    monkeypatch.setattr(ws_mod.stt_provider, "transcribe", lambda audio: "今天天氣如何")

    async def fake_stream(message, state, memory, emit, register_queue=None):
        assert message == "今天天氣如何"  # the transcript drives the turn
        await emit({"type": "reply_chunk", "text": "很好喔"})
        await emit({"type": "turn_end"})

    monkeypatch.setattr(ws_mod, "run_turn_streaming", fake_stream)

    with client.websocket_connect("/ws") as ws:
        ws.send_bytes(b"FAKE_WEBM_AUDIO")

        transcript = ws.receive_json()
        assert transcript["type"] == "transcript"
        assert transcript["text"] == "今天天氣如何"

        assert ws.receive_json()["type"] == "reply_chunk"
        assert ws.receive_json()["type"] == "turn_end"


def test_ws_silent_audio_no_turn(client, monkeypatch):
    monkeypatch.setattr(ws_mod.stt_provider, "transcribe", lambda audio: "   ")

    async def fake_stream(*args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("no turn should start on silent audio")

    monkeypatch.setattr(ws_mod, "run_turn_streaming", fake_stream)

    with client.websocket_connect("/ws") as ws:
        ws.send_bytes(b"SILENCE")
        transcript = ws.receive_json()
        assert transcript["type"] == "transcript"
        assert transcript["text"] == ""


def test_ws_blank_text_ignored(client, monkeypatch):
    async def fake_stream(message, state, memory, emit, register_queue=None):
        await emit({"type": "reply_chunk", "text": "有回覆"})
        await emit({"type": "turn_end"})

    monkeypatch.setattr(ws_mod, "run_turn_streaming", fake_stream)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "text", "text": "   "})  # whitespace only → ignored
        ws.send_json({"type": "text", "text": "真的訊息"})
        assert ws.receive_json()["type"] == "reply_chunk"


def test_ws_interrupt_stops_turn(client, monkeypatch):
    cancelled = {"value": False}

    class _TrackingQueue:
        def cancel_all(self):
            cancelled["value"] = True

    async def slow_stream(message, state, memory, emit, register_queue=None):
        if register_queue:
            register_queue(_TrackingQueue())
        await asyncio.sleep(5)  # long enough to be interrupted mid-flight
        await emit({"type": "turn_end"})

    monkeypatch.setattr(ws_mod, "run_turn_streaming", slow_stream)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "text", "text": "開始"})
        ws.send_json({"type": "interrupt"})
        stopped = ws.receive_json()
        assert stopped["type"] == "stopped"
        assert cancelled["value"] is True  # the TTS queue was cancelled too
