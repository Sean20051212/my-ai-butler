import asyncio

from openai import OpenAI

from backend.config import CHAT_MODEL, OLLAMA_BASE_URL
from backend.services.llm.base import BaseLLMProvider

# Sentinel so a blocking generator drained in a thread can signal "no more".
_STREAM_DONE = object()


class OllamaProvider(BaseLLMProvider):
    """Local inference via Ollama's OpenAI-compatible endpoint."""

    def __init__(self) -> None:
        # Module-equivalent client, re-used across requests.
        self._client = OpenAI(
            base_url=f"{OLLAMA_BASE_URL}/v1",
            api_key="ollama",
        )

    def chat(self, messages: list) -> str:
        # Plain-text output ([emotion]spoken text); no JSON mode now that the
        # reply is streamed sentence by sentence.
        completion = self._client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.4,
        )
        return completion.choices[0].message.content

    async def chat_stream(self, messages: list):
        """Yield reply text chunks as the model produces them.

        The OpenAI client's stream is a blocking iterator, so each ``next`` is
        pushed off the event loop with ``asyncio.to_thread``; that keeps the WS
        receive loop (and barge-in) responsive while tokens arrive.
        """
        stream = await asyncio.to_thread(
            self._client.chat.completions.create,
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.4,
            stream=True,
        )

        def _next():
            try:
                return next(stream)
            except StopIteration:
                return _STREAM_DONE

        while True:
            chunk = await asyncio.to_thread(_next)
            if chunk is _STREAM_DONE:
                break
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
