from backend.services.llm.parsing import (
    parse_emotion_tag,
    try_resolve_emotion_prefix,
)


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


# --- streaming prefix resolver ---------------------------------------------

def test_resolve_waits_while_tag_incomplete():
    # "[ha" could still become "[happy]" — keep buffering.
    assert try_resolve_emotion_prefix("[ha") is None


def test_resolve_when_tag_completes():
    assert try_resolve_emotion_prefix("[happy]哈") == ("happy", "哈")


def test_resolve_no_bracket_is_immediate():
    # First real char isn't a bracket → there's no tag, resolve now.
    assert try_resolve_emotion_prefix("哈囉") == ("neutral", "哈囉")


def test_resolve_waits_on_leading_whitespace_only():
    assert try_resolve_emotion_prefix("   ") is None


def test_resolve_gives_up_after_max_wait():
    # A bracket opened but never closed for too long → treat as plain text.
    long_open = "[" + "x" * 20
    emotion, text = try_resolve_emotion_prefix(long_open)
    assert emotion == "neutral"
    assert text == long_open
