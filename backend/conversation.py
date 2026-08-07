"""One turn of conversation, transport-agnostic.

``run_turn`` holds the full perceive → think → speak pipeline that used to live
inline in the ``/chat`` route.  Pulling it out lets both the HTTP endpoint and
the WebSocket endpoint drive the same brain without duplicating logic.

The heavy service singletons (LLM, vision, TTS cache) are created once at import
and shared across transports; tests monkeypatch them here.
"""

import asyncio
import base64
import json
import re
import time

from backend.services.llm import get_dynamic_system_prompt, get_llm_provider
from backend.services.tts import TTSCache, get_tts_provider
from backend.services.vision import get_vision_chain
from backend.utils.text import converter

llm_provider = get_llm_provider()
vision_chain = get_vision_chain()
tts_cache    = TTSCache(get_tts_provider())

# Model artefacts to strip before parsing the reply JSON.
_ARTIFACT_RE = re.compile(
    r"(/INFO/|<\|im_start\|>|<\|im_end\|>|<\|.*?\|>|\[System\]|\[Assistant\])"
)


async def run_turn(message: str, state, memory) -> dict:
    """Run one full conversation turn and return the result dict.

    The dict always contains at least ``reply`` and ``emotion``; when TTS
    succeeds it also carries ``audio_base64``.  Any failure degrades to a safe
    fallback reply rather than raising, so every transport behaves identically.
    """
    start_time = time.time()

    try:
        # ── Perceive on demand (DOM → accessibility → VLM) ──────────────
        # Run off the event loop: sources may block (HTTP/screenshot) and the
        # Playwright sync API refuses to run inside a running asyncio loop.
        vision = await asyncio.to_thread(vision_chain.capture)
        if vision is not None:
            state.latest_vision = vision

        # ── Build message list ──────────────────────────────────────────
        system_prompt = get_dynamic_system_prompt(state)

        memory_context = memory.query(message)
        if memory_context:
            system_prompt += f"\n\n【相關記憶】\n{memory_context}"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(state.chat_history)
        messages.append({"role": "user", "content": message})

        # ── LLM call ───────────────────────────────────────────────────
        raw_content = llm_provider.chat(messages)

        # Strip model artefacts and convert to Traditional Chinese
        raw_content = _ARTIFACT_RE.sub("", raw_content)
        raw_content = converter.convert(raw_content)

        result     = json.loads(raw_content)
        reply_text = result.get("reply", "").strip()
        if not reply_text:
            reply_text      = "嗯...（沉默了一下）"
            result["reply"] = reply_text

        # ── State updates ──────────────────────────────────────────────
        state.add_to_history(message, reply_text)
        state.apply_emotion(result.get("emotion", "neutral"))

        elapsed = time.time() - start_time
        print(f"\n{'='*40}")
        print(f"Thinking: {elapsed:.2f}s")
        print(f"Vision:   {state.latest_vision}")
        print(f"Thought:  {result.get('inner_thought', '')}")
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
