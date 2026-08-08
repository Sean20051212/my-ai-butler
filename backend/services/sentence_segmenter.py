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
    def __init__(
        self,
        faster_first_response: bool = True,
        max_buffer: int = 60,
        min_len: int = 0,
    ):
        # min_len: sentences shorter than this are merged forward instead of
        # emitted alone, so slow TTS isn't handed tiny fragments like "哼哼"
        # (which synthesise oddly and leave an awkward gap before the real
        # first sentence). 0 disables merging.
        self.faster_first_response = faster_first_response
        self.max_buffer = max_buffer
        self.min_len = min_len
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

        # First-sentence fast path: split at the first comma — but only if the
        # head is already substantial, so we never emit a tiny "哼哼，" fragment.
        if self._is_first and self.faster_first_response:
            m = _COMMA_RE.search(self._buffer)
            if m:
                head = self._buffer[: m.end()].strip()
                if _has_speakable(head) and len(head) >= self.min_len:
                    self._buffer = self._buffer[m.end():]
                    out.append(self._make(head))

        # Normal path: extract complete sentences, merging any that fall short
        # of min_len into the following one (don't advance past a short chunk).
        text = self._buffer
        chunk_start = 0
        for match in _SENTENCE_RE.finditer(text):
            candidate = text[chunk_start: match.end()].strip()
            if _has_speakable(candidate) and len(candidate) >= self.min_len:
                out.append(self._make(candidate))
                chunk_start = match.end()
        self._buffer = text[chunk_start:]

        # Guard: no boundary for too long → force-flush so we never stall.
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
