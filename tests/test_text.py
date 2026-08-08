from backend.utils.text import preprocess_for_tts


def test_strips_fullwidth_parenthetical_stage_direction():
    # Narration in （）must not survive into the TTS text.
    assert preprocess_for_tts("主人你回來啦（開心地轉圈）我好想你") == "主人你回來啦我好想你"


def test_strips_halfwidth_parenthetical():
    assert "笑" not in preprocess_for_tts("今天天氣真好(笑)好想出門")


def test_keeps_english_words_intact():
    # CosyVoice2 is multilingual; English should pass through as words.
    assert "OK" in preprocess_for_tts("好的！這件事交給我 OK?")


def test_clean_fallback_survives_preprocessing():
    # The empty-reply fallback must remain speakable (non-empty) after cleaning.
    assert preprocess_for_tts("嗯……讓我想一下。")


def test_strips_misplaced_emotion_tag():
    # A tag that leaked into the middle must not be read aloud as "happy".
    out = preprocess_for_tts("我很好[happy]謝謝關心")
    assert "happy" not in out.lower()
    assert "謝謝關心" in out
