"""Incremental sentence segmentation for the streaming TTS pipeline.

Consumes an LLM token stream and yields complete sentences the moment each one
is finished, so synthesis can start on sentence 1 while the model is still
writing sentence 2.  Modelled on Open-LLM-VTuber's ``SentenceDivider`` but
rewritten small and Chinese-first for this project's service layer.

Design notes:
- End punctuation is 。！？…!? — ASCII "." is deliberately excluded so decimals
  and abbreviations (3.14, e.g.) don't cause false splits in a Chinese-primary
  butler.
- ``faster_first_response`` splits the very first sentence at its first comma,
  trading semantic completeness for a faster first audio segment.
- A max-buffer guard force-flushes when no end punctuation has appeared for a
  long time (e.g. a code block), so the pipeline never stalls forever.
"""

import re
from dataclasses import dataclass
from typing import AsyncIterator

_END_PUNCT = "。！？…!?"
# A run of any characters up to and including one or more end-punctuation marks.
_SENTENCE_RE = re.compile(r".+?[" + re.escape(_END_PUNCT) + r"]+", re.S)
# Commas the first-sentence fast path may split on.
_COMMAS = "，,、；;"
_COMMA_RE = re.compile(r"[" + re.escape(_COMMAS) + r"]")
# Characters that don't count as speakable content (punctuation / whitespace).
_NON_SPEAKABLE_RE = re.compile(r"[\s" + re.escape(_END_PUNCT + _COMMAS + "。，、「」『』（）()…—～·.") + r"]")


def _has_speakable(text: str) -> bool:
    """True if *text* has any content worth synthesising (not just punctuation)."""
    return bool(_NON_SPEAKABLE_RE.sub("", text).strip())


@dataclass
class SegmentedSentence:
    text: str
    is_first: bool


class SentenceSegmenter:
    def __init__(self, faster_first_response: bool = True, max_buffer: int = 60):
        self.faster_first_response = faster_first_response
        self.max_buffer = max_buffer
        self._buffer = ""
        self._is_first = True

    async def process_stream(
        self, token_stream: AsyncIterator[str]
    ) -> AsyncIterator[SegmentedSentence]:
        async for token in token_stream:
            self._buffer += token
            for sentence in self._drain():
                yield sentence
        # Stream ended: emit whatever remains as the last sentence.
        tail = self._buffer.strip()
        self._buffer = ""
        if _has_speakable(tail):
            yield self._make(tail)

    def _drain(self) -> list[SegmentedSentence]:
        """Pull every sentence the buffer can currently yield (keeps a remainder)."""
        out: list[SegmentedSentence] = []

        # First-sentence fast path: split at the first comma if one is present.
        if self._is_first and self.faster_first_response:
            m = _COMMA_RE.search(self._buffer)
            if m:
                head = self._buffer[: m.end()].strip()
                self._buffer = self._buffer[m.end():]
                if _has_speakable(head):
                    out.append(self._make(head))

        # Normal path: extract every complete (end-punctuated) sentence.
        last = 0
        for match in _SENTENCE_RE.finditer(self._buffer):
            sentence = match.group().strip()
            last = match.end()
            if _has_speakable(sentence):
                out.append(self._make(sentence))
        if last:
            self._buffer = self._buffer[last:]

        # Guard: no punctuation for too long → force-flush so we never stall.
        if len(self._buffer) >= self.max_buffer:
            chunk = self._buffer.strip()
            self._buffer = ""
            if _has_speakable(chunk):
                out.append(self._make(chunk))

        return out

    def _make(self, text: str) -> SegmentedSentence:
        sentence = SegmentedSentence(text=text, is_first=self._is_first)
        self._is_first = False
        return sentence

    def reset(self) -> None:
        self._buffer = ""
        self._is_first = True
