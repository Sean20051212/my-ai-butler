from backend.services.llm.parsing import parse_emotion_tag


def test_parses_leading_tag():
    assert parse_emotion_tag("[happy]哈囉主人") == ("happy", "哈囉主人")


def test_tolerates_whitespace_and_fullwidth_brackets():
    assert parse_emotion_tag("  ［surprised］ 咦？") == ("surprised", "咦？")


def test_no_tag_defaults_neutral_keeps_text():
    assert parse_emotion_tag("就是一句話") == ("neutral", "就是一句話")


def test_unknown_emotion_stripped_but_neutral():
    emotion, text = parse_emotion_tag("[excited]太好了")
    assert emotion == "neutral"
    assert text == "太好了"


def test_case_insensitive_emotion():
    assert parse_emotion_tag("[HAPPY]耶") == ("happy", "耶")


def test_empty_input():
    assert parse_emotion_tag("") == ("neutral", "")


def test_tag_only_gives_empty_text():
    assert parse_emotion_tag("[sad]") == ("sad", "")
