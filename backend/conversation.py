"""One turn of conversation, transport-agnostic.

``run_turn`` holds the full perceive → think → speak pipeline that used to live
inline in the ``/chat`` route.  Pulling it out lets both the HTTP endpoint and
the WebSocket endpoint drive the same brain without duplicating logic.

The heavy service singletons (LLM, vision, TTS cache) are created once at import
and shared across transports; tests monkeypatch them here.
"""

import asyncio
import base64
import re
import time

from backend.services.llm import get_dynamic_system_prompt, get_llm_provider
from backend.services.llm.parsing import parse_emotion_tag, try_resolve_emotion_prefix
from backend.services.sentence_segmenter import SentenceSegmenter
from backend.services.tts import TTSCache, get_tts_provider
from backend.services.tts_task_queue import TTSTaskQueue
from backend.services.vision import get_vision_chain
from backend.utils.text import converter

llm_provider = get_llm_provider()
vision_chain = get_vision_chain()
tts_cache    = TTSCache(get_tts_provider())

# Model artefacts to strip before parsing the reply JSON.
_ARTIFACT_RE = re.compile(
    r"(/INFO/|<\|im_start\|>|<\|im_end\|>|<\|.*?\|>|\[System\]|\[Assistant\])"
)


async def _prepare_messages(message: str, state, memory) -> list:
    """Perceive on demand and build the OpenAI-format message list.

    Shared by the blocking (``run_turn``) and streaming (``run_turn_streaming``)
    paths so perception, memory injection and the role card stay identical.
    """
    # Run vision off the event loop: sources may block (HTTP/screenshot) and the
    # Playwright sync API refuses to run inside a running asyncio loop.
    vision = await asyncio.to_thread(vision_chain.capture)
    if vision is not None:
        state.latest_vision = vision

    system_prompt = get_dynamic_system_prompt(state)
    memory_context = memory.query(message)
    if memory_context:
        system_prompt += f"\n\n【相關記憶】\n{memory_context}"

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(state.chat_history)
    messages.append({"role": "user", "content": message})
    return messages


async def run_turn(message: str, state, memory) -> dict:
    """Run one full conversation turn and return the result dict.

    The dict always contains at least ``reply`` and ``emotion``; when TTS
    succeeds it also carries ``audio_base64``.  Any failure degrades to a safe
    fallback reply rather than raising, so every transport behaves identically.
    """
    start_time = time.time()

    try:
        messages = await _prepare_messages(message, state, memory)

        # ── LLM call ───────────────────────────────────────────────────
        raw_content = llm_provider.chat(messages)

        # Strip model artefacts and convert to Traditional Chinese
        raw_content = _ARTIFACT_RE.sub("", raw_content)
        raw_content = converter.convert(raw_content)

        # New format: "[emotion]spoken text" (no JSON). Parsing is forgiving —
        # a missing/unknown tag falls back to neutral with the text intact.
        emotion, reply_text = parse_emotion_tag(raw_content)
        reply_text = reply_text.strip()
        if not reply_text:
            # Diagnostic on the failure case: show the model's raw output so we
            # can tell an empty response from a formatting slip.
            print(f"[空回覆] LLM 原始輸出：{raw_content!r}")
            # Clean, speakable fallback: no parenthetical stage direction (which
            # TTS would either read aloud or choke on into a short screech).
            reply_text = "嗯……讓我想一下。"

        result = {"reply": reply_text, "emotion": emotion}

        # ── State updates ──────────────────────────────────────────────
        state.add_to_history(message, reply_text)
        state.apply_emotion(emotion)

        elapsed = time.time() - start_time
        print(f"\n{'='*40}")
        print(f"Thinking: {elapsed:.2f}s")
        print(f"Vision:   {state.latest_vision}")
        print(f"Emotion:  {emotion}")
        print(f"Reply:    {reply_text}")
        print(f"{'='*40}\n")

        # ── TTS (cache-aware) ──────────────────────────────────────────
        audio_bytes = tts_cache.get_audio(reply_text)
        if audio_bytes:
            result["audio_base64"] = base64.b64encode(audio_bytes).decode("utf-8")

        # ── Persist memory ─────────────────────────────────────────────
        memory.write_memory(message, reply_text, state.current_mood, state)

        return result

    except Exception as exc:
        print(f"Chat error: {exc}")
        return {"reply": "嗚...我的大腦好像有點當機了...", "emotion": "sad"}


async def _emotion_then_text(token_stream, on_emotion):
    """Strip the leading ``[emotion]`` from the front of a token stream.

    Buffers only until the tag resolves, calls *on_emotion* once with the
    detected emotion, then yields every subsequent chunk of spoken text.
    """
    buffer = ""
    resolved = False
    async for token in token_stream:
        if resolved:
            yield token
            continue
        buffer += token
        outcome = try_resolve_emotion_prefix(buffer)
        if outcome is not None:
            emotion, rest = outcome
            await on_emotion(emotion)
            resolved = True
            if rest:
                yield rest
    if not resolved:
        # Stream ended before the tag resolved (very short reply / no tag).
        emotion, rest = parse_emotion_tag(buffer)
        await on_emotion(emotion)
        if rest:
            yield rest


async def run_turn_streaming(message, state, memory, emit, register_queue=None):
    """Stream one turn: emotion first, then sentence-by-sentence text + audio.

    *emit* is an async ``dict -> None`` sink (the WebSocket's ``send_json``).
    Emits: ``emotion`` → ``reply_chunk`` (per sentence, in order) → ``audio``
    (per sentence, parallel synth but delivered in order) → ``turn_end``.

    *register_queue*, if given, is called with the TTSTaskQueue so the caller
    can ``cancel_all()`` it on barge-in.
    """
    try:
        messages = await _prepare_messages(message, state, memory)

        collected: list[str] = []
        emotion_seen = {"value": "neutral"}

        async def on_emotion(emotion):
            emotion_seen["value"] = emotion
            state.apply_emotion(emotion)
            await emit({"type": "emotion", "emotion": emotion})

        async def on_audio_ready(seq, audio):
            print(f"[TTS] seq={seq} {'OK ' + str(len(audio)) + 'B' if audio else 'SILENT/FAIL'}")
            await emit({
                "type": "audio",
                "seq": seq,
                "base64": base64.b64encode(audio).decode("utf-8") if audio else None,
            })

        tts_queue = TTSTaskQueue(tts_cache.get_audio, on_audio_ready)
        if register_queue is not None:
            register_queue(tts_queue)

        # Segment by whole sentences (no tiny comma fragments), merging any
        # sentence shorter than min_len so slow TTS gets coherent chunks.
        segmenter = SentenceSegmenter(faster_first_response=False, min_len=8)
        text_stream = _emotion_then_text(llm_provider.chat_stream(messages), on_emotion)

        async for sentence in segmenter.process_stream(text_stream):
            # Per-sentence artefact strip + Simplified→Traditional conversion.
            clean = converter.convert(_ARTIFACT_RE.sub("", sentence.text)).strip()
            if not clean:
                continue
            print(f"[SEG] {clean!r}")
            collected.append(clean)
            await emit({"type": "reply_chunk", "text": clean})
            tts_queue.submit(clean)

        await tts_queue.wait_all()

        full_reply = "".join(collected).strip()
        if not full_reply:
            full_reply = "嗯……讓我想一下。"
            await emit({"type": "reply_chunk", "text": full_reply})

        state.add_to_history(message, full_reply)
        memory.write_memory(message, full_reply, state.current_mood, state)
        await emit({"type": "turn_end"})

    except asyncio.CancelledError:
        raise  # barge-in — stop emitting immediately
    except Exception as exc:
        print(f"Streaming turn error: {exc}")
        await emit({"type": "reply_chunk", "text": "嗚...我的大腦好像有點當機了..."})
        await emit({"type": "turn_end"})
