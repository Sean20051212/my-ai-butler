"""Parallel TTS synthesis with in-order delivery.

Each submitted sentence is synthesised on its own task so a short sentence 3
doesn't wait behind a long sentence 1 — but results are still delivered in
submission order, because the frontend must play sentence 2 before sentence 3.

Adapted from Open-LLM-VTuber's ``TTSTaskManager`` to this project's synchronous
provider: synthesis is a blocking ``str -> bytes | None`` callable (our
``TTSCache.get_audio``, which also preprocesses and caches), run off the event
loop via ``asyncio.to_thread``.  A silent/failed sentence still consumes a
sequence number and is delivered as ``None`` so ordering never deadlocks.
"""

import asyncio
from typing import Awaitable, Callable, Optional

# (text) -> audio bytes, or None when the text is silent / synthesis failed.
Synthesize = Callable[[str], Optional[bytes]]
# (sequence_number, audio_bytes_or_None) -> awaitable
OnAudioReady = Callable[[int, Optional[bytes]], Awaitable[None]]


class TTSTaskQueue:
    def __init__(
        self,
        synthesize: Synthesize,
        on_audio_ready: OnAudioReady,
        max_concurrency: int = 1,
    ) -> None:
        self._synthesize = synthesize
        self._on_audio_ready = on_audio_ready
        # Cap concurrent synthesis. Default 1: the local CosyVoice server holds a
        # single non-thread-safe CUDA model, so overlapping requests would corrupt
        # output — and one GPU model can't truly parallelise anyway. Serialising
        # here still gives the win: sentence 1 synthesises and plays while later
        # sentences wait their turn, instead of everything after the full reply.
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._sequence_counter = 0
        self._next_to_send = 0
        self._buffered: dict[int, Optional[bytes]] = {}
        self._tasks: list[asyncio.Task] = []
        self._lock = asyncio.Lock()
        self._cancelled = False

    def submit(self, text: str) -> int:
        """Queue a sentence for synthesis; returns its sequence number."""
        seq = self._sequence_counter
        self._sequence_counter += 1
        self._tasks.append(asyncio.create_task(self._synthesize_and_buffer(text, seq)))
        return seq

    async def _synthesize_and_buffer(self, text: str, seq: int) -> None:
        try:
            async with self._semaphore:
                audio = await asyncio.to_thread(self._synthesize, text)
        except asyncio.CancelledError:
            raise  # barge-in — drop silently, deliver nothing
        except Exception as exc:  # pragma: no cover - defensive
            print(f"TTS 合成失敗（seq {seq}）：{exc}")
            audio = None

        async with self._lock:
            if self._cancelled:
                return
            self._buffered[seq] = audio
            # Flush every contiguous ready sequence, in order.
            while not self._cancelled and self._next_to_send in self._buffered:
                ready_seq = self._next_to_send
                ready_audio = self._buffered.pop(ready_seq)
                self._next_to_send += 1
                await self._on_audio_ready(ready_seq, ready_audio)

    async def wait_all(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def cancel_all(self) -> None:
        """Cancel pending synthesis and drop buffered results (barge-in)."""
        self._cancelled = True
        for task in self._tasks:
            if not task.done():
                task.cancel()
        self._tasks.clear()
        self._buffered.clear()
        self._sequence_counter = 0
        self._next_to_send = 0
