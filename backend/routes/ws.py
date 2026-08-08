"""WebSocket transport for the butler.

A persistent channel is what makes streaming audio and barge-in possible; the
one-shot HTTP ``/chat`` route cannot stop a reply mid-flight.  It carries both
typed text and microphone audio, and is shaped for the streaming pipeline
(task 8) and barge-in (task 9) to come:

Client → Server
    {"type": "text", "text": "..."}   a typed message
    {"type": "interrupt"}             stop the current reply now
    <binary frame>                    one complete recorded utterance (any
                                      container faster-whisper can decode, e.g.
                                      webm/opus from MediaRecorder)

Server → Client
    {"type": "transcript", "text": ...}          what STT heard from the audio
    {"type": "reply", "text": ..., "emotion": ...}
    {"type": "audio", "seq": N, "base64": ...}   one audio segment (0-based)
    {"type": "turn_end"}                          this turn produced all output
    {"type": "stopped"}                           the turn was interrupted

Each connection runs at most one turn at a time; a new message (typed or
spoken) or an ``interrupt`` cancels any in-flight turn.  The turn runs as a
background task so the receive loop stays free to catch the interrupt while
audio is streaming.
"""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.conversation import run_turn_streaming
from backend.services.stt import get_stt_provider

router = APIRouter()

# One STT provider per process. Instantiation is cheap — the whisper model is
# loaded lazily on the first transcribe() — so importing this module (and the
# test suite) stays fast and free of the optional faster-whisper dependency.
stt_provider = get_stt_provider()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    state = ws.app.state.character
    memory = ws.app.state.memory
    current_task: asyncio.Task | None = None
    current_queue = None  # the in-flight turn's TTSTaskQueue, for barge-in

    async def cancel_current() -> None:
        nonlocal current_task, current_queue
        # Cancel pending TTS synthesis first so nothing new is delivered, then
        # cancel the turn task itself.
        if current_queue is not None:
            current_queue.cancel_all()
        if current_task and not current_task.done():
            current_task.cancel()
            try:
                await current_task
            except (asyncio.CancelledError, Exception):
                pass
            await ws.send_json({"type": "stopped"})
        current_task = None
        current_queue = None

    async def start_turn(text: str) -> None:
        nonlocal current_task, current_queue
        await cancel_current()  # a new message supersedes the old turn

        def register_queue(queue):
            nonlocal current_queue
            current_queue = queue

        current_task = asyncio.create_task(
            run_turn_streaming(text, state, memory, ws.send_json, register_queue)
        )

    try:
        while True:
            # Raw receive() so we can handle both binary audio and text control
            # frames on the same socket.
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break

            audio = msg.get("bytes")
            if audio is not None:
                # A complete recorded utterance. Transcription blocks for a few
                # seconds (CPU whisper), so run it off the event loop.
                text = (await asyncio.to_thread(stt_provider.transcribe, audio)).strip()
                await ws.send_json({"type": "transcript", "text": text})
                if text:
                    await start_turn(text)
                continue

            raw = msg.get("text")
            if raw is None:
                continue
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue

            mtype = data.get("type")
            if mtype == "text":
                text = (data.get("text") or "").strip()
                if text:
                    await start_turn(text)
            elif mtype == "interrupt":
                await cancel_current()

    except WebSocketDisconnect:
        pass
    finally:
        if current_task and not current_task.done():
            current_task.cancel()
