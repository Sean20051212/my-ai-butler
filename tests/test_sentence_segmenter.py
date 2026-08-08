import pytest

from backend.services.sentence_segmenter import SentenceSegmenter


async def _stream(chunks):
    for c in chunks:
        yield c


async def _collect(segmenter, chunks):
    return [s async for s in segmenter.process_stream(_stream(chunks))]


@pytest.mark.asyncio
async def test_three_sentences_across_chunks():
    # Sentence boundaries fall in the middle of chunks; expect exactly 3.
    seg = SentenceSegmenter(faster_first_response=False)
    chunks = ["你好啊主", "人。今天", "天氣真好！我們出", "去走走吧？"]
    out = await _collect(seg, chunks)
    assert [s.text for s in out] == ["你好啊主人。", "今天天氣真好！", "我們出去走走吧？"]


@pytest.mark.asyncio
async def test_faster_first_response_splits_at_comma():
    seg = SentenceSegmenter(faster_first_response=True)
    out = await _collect(seg, ["哼哼，", "主人你來啦。"])
    assert out[0].text == "哼哼，"
    assert out[0].is_first is True
    assert out[1].text == "主人你來啦。"
    assert out[1].is_first is False


@pytest.mark.asyncio
async def test_no_comma_split_when_disabled():
    seg = SentenceSegmenter(faster_first_response=False)
    out = await _collect(seg, ["哼哼，主人你來啦。"])
    assert [s.text for s in out] == ["哼哼，主人你來啦。"]
    assert out[0].is_first is True


@pytest.mark.asyncio
async def test_trailing_text_without_punctuation_is_flushed():
    seg = SentenceSegmenter(faster_first_response=False)
    out = await _collect(seg, ["這句有句號。", "這句沒有標點結尾"])
    assert [s.text for s in out] == ["這句有句號。", "這句沒有標點結尾"]


@pytest.mark.asyncio
async def test_punctuation_only_is_skipped():
    seg = SentenceSegmenter(faster_first_response=False)
    out = await _collect(seg, ["。。。", "！！"])
    assert out == []


@pytest.mark.asyncio
async def test_short_sentences_merged_by_min_len():
    seg = SentenceSegmenter(faster_first_response=False, min_len=8)
    out = await _collect(seg, ["好。壞。", "可以嗎？再想想吧。"])
    # "好。"/"壞。" are too short to stand alone → merged up to min_len.
    assert out[0].text == "好。壞。可以嗎？"
    assert out[1].text == "再想想吧。"  # trailing short chunk flushed at the end


@pytest.mark.asyncio
async def test_faster_first_does_not_split_tiny_head():
    seg = SentenceSegmenter(faster_first_response=True, min_len=8)
    out = await _collect(seg, ["哼哼，主人早安！今天天氣真好？"])
    # "哼哼，" is below min_len, so no tiny fragment — first segment is a full sentence.
    assert out[0].text == "哼哼，主人早安！"


@pytest.mark.asyncio
async def test_max_buffer_force_flush():
    seg = SentenceSegmenter(faster_first_response=False, max_buffer=10)
    long_no_punct = "一二三四五六七八九十十一十二"  # >10 chars, no end punctuation
    out = await _collect(seg, [long_no_punct])
    assert len(out) >= 1
    assert "".join(s.text for s in out).replace(" ", "") == long_no_punct
