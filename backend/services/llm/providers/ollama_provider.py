from openai import OpenAI

from backend.config import CHAT_MODEL, OLLAMA_BASE_URL
from backend.services.llm.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Local inference via Ollama's OpenAI-compatible endpoint."""

    def __init__(self) -> None:
        # Module-equivalent client, re-used across requests.
        self._client = OpenAI(
            base_url=f"{OLLAMA_BASE_URL}/v1",
            api_key="ollama",
        )

    def chat(self, messages: list) -> str:
        completion = self._client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        return completion.choices[0].message.content
