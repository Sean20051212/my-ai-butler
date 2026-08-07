import re
import opencc

# Simplified → Traditional Chinese (Taiwan standard), module-level singleton
converter = opencc.OpenCC("s2twp")

_SAFE_PUNCT = set('，。！？、；：「」『』【】《》…—～')
# Latin punctuation/joiners kept inside/around English words so they read as words
_KEEP_LATIN = set(" '-.&")


def preprocess_for_tts(text: str) -> str:
    """Clean LLM output for CosyVoice2 TTS.

    Strips Markdown and drops emoji / unsupported symbols, but *keeps* English
    words intact: CosyVoice2 is multilingual and pronounces English as words,
    so we no longer transliterate letters to Mandarin phonetics (that made
    English read out letter-by-letter with long gaps).
    """
    # 1. Strip Markdown formatting
    text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.*?\)', r'\1', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

    # 1b. Drop parenthetical stage directions like （沉默了一下）or (笑) — these
    #     are narration, not speech, and must not be read aloud. Non-nested only.
    text = re.sub(r'[（(][^（(）)]*[）)]', '', text)

    # 2. Keep CJK, kana, safe punctuation, digits, ASCII letters and latin
    #    joiners; replace anything else (emoji, rare symbols) with '，'
    filtered = []
    for c in text:
        cp = ord(c)
        if (0x4E00 <= cp <= 0x9FFF or   # CJK Unified Ideographs
                0x3400 <= cp <= 0x4DBF or   # CJK Extension A
                0xF900 <= cp <= 0xFAFF or   # CJK Compatibility
                0x3040 <= cp <= 0x30FF or   # Hiragana + Katakana
                c in _SAFE_PUNCT or
                c.isdigit() or
                ('a' <= c.lower() <= 'z') or
                c in _KEEP_LATIN):
            filtered.append(c)
        else:
            filtered.append('，')
    text = ''.join(filtered)

    # 3. Collapse repeated punctuation / whitespace and trim
    text = re.sub(r'[，。！？]{2,}', '。', text)
    text = re.sub(r'\s{2,}', ' ', text)
    text = text.strip('， ')

    return text
