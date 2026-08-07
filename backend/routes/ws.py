"""WebSocket transport for the butler.

A persistent channel is what makes streaming audio and barge-in possible; the
one-shot HTTP ``/chat`` route cannot stop a reply mid-flight.  This stage wires
up the *text* path only — voice input (mic frames → STT) arrives in a later
stage — but the message protocol below is already shaped to carry everything
the streaming pipeline (task 8) and barge-in (task 9) will need:

Client → Server
    {"type": "text", "text": "..."}   a typed message
    {"type": "interrupt"}             stop the current reply now

Server → Client
    {"type": "reply", "text": ..., "emotion": ...}
    {"type": "audio", "seq": N, "base64": ...}   one audio segment (0-based)
    {"type": "turn_end"}                          this turn produced all output
    {"type": "stopped"}                           the turn was interrupted

Each connection runs at most one turn at a time; a new ``text`` (or an
``interrupt``) cancels any in-flight turn.  The turn runs as a background task
so the receive loop stays free to catch the interrupt while audio is streaming.
"""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.conversation import run_turn

router = APIRouter()


async def _run_and_stream(ws: WebSocket, message: str, state, memory) -> None:
    """Run one turn and push its output down the socket.

    run_turn still returns the whole reply at once (LLM streaming is task 8), so
    this emits a single audio segment (seq 0).  The protocol already numbers
    segments, so task 8 can emit many without any client change.  Send failures
    (client vanished) are swallowed — the connection teardown handles it.
    """
    try:
        result = await run_turn(message, state, memory)
        await ws.send_json({
            "type": "reply",
            "text": result.get("reply", ""),
            "emotion": result.get("emotion", "neutral"),
        })
        audio_b64 = result.get("audio_base64")
        if audio_b64:
            await ws.send_json({"type": "audio", "seq": 0, "base64": audio_b64})
        await ws.send_json({"type": "turn_end"})
    except asyncio.CancelledError:
        raise  # interrupted — let the canceller proceed, emit nothing further
    except Exception as exc:  # pragma: no cover - defensive on a dead socket
        print(f"WS turn error: {exc}")


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    state = ws.app.state.character
    memory = ws.app.state.memory
    current_task: asyncio.Task | None = None

    async def cancel_current() -> None:
        nonlocal current_task
        if current_task and not current_task.done():
            current_task.cancel()
            try:
                await current_task
            except (asyncio.CancelledError, Exception):
                pass
            await ws.send_json({"type": "stopped"})
        current_task = None

    try:
        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")

            if mtype == "text":
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                await cancel_current()  # new message supersedes the old turn
                current_task = asyncio.create_task(
                    _run_and_stream(ws, text, state, memory)
                )

            elif mtype == "interrupt":
                await cancel_current()

    except WebSocketDisconnect:
        if current_task and not current_task.done():
            current_task.cancel()
