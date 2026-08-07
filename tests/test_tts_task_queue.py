import asyncio
import time

import pytest

from backend.services.tts_task_queue import TTSTaskQueue


@pytest.mark.asyncio
async def test_parallel_synth_ordered_delivery():
    # Sentence 3 finishes first, sentence 1 last — delivery must still be 1→2→3.
    durations = {"s0": 0.15, "s1": 0.10, "s2": 0.05}

    def synth(text):
        time.sleep(durations[text])  # blocking, runs in a worker thread
        return text.encode()

    delivered = []

    async def on_ready(seq, audio):
        delivered.append((seq, audio))

    q = TTSTaskQueue(synth, on_ready)
    q.submit("s0")
    q.submit("s1")
    q.submit("s2")
    await q.wait_all()

    assert [seq for seq, _ in delivered] == [0, 1, 2]
    assert [audio for _, audio in delivered] == [b"s0", b"s1", b"s2"]


@pytest.mark.asyncio
async def test_silent_segment_still_advances_order():
    def synth(text):
        return None if text == "silent" else text.encode()

    delivered = []

    async def on_ready(seq, audio):
        delivered.append((seq, audio))

    q = TTSTaskQueue(synth, on_ready)
    q.submit("a")
    q.submit("silent")
    q.submit("c")
    await q.wait_all()

    assert [seq for seq, _ in delivered] == [0, 1, 2]
    assert delivered[1] == (1, None)  # silent delivered as None, keeps order


@pytest.mark.asyncio
async def test_cancel_all_stops_pending_callbacks():
    def synth(text):
        time.sleep(0.2)
        return b"x"

    delivered = []

    async def on_ready(seq, audio):
        delivered.append(seq)

    q = TTSTaskQueue(synth, on_ready)
    q.submit("a")
    q.submit("b")
    q.cancel_all()

    await asyncio.sleep(0.3)  # let any leaked task try (and fail) to deliver
    assert delivered == []
    assert q._next_to_send == 0  # counters reset for the next turn
