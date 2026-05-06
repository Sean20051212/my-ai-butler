import re
import opencc

# Simplified → Traditional Chinese (Taiwan standard), module-level singleton
converter = opencc.OpenCC("s2twp")

_EN_LETTER_ZH = {
    'a': '誒', 'b': '逼', 'c': '西',  'd': '低',    'e': '伊',
    'f': '誒夫', 'g': '機', 'h': '誒曲', 'i': '愛',  'j': '傑',
    'k': '誒',  'l': '誒喔', 'm': '誒母', 'n': '恩',  'o': '歐',
    'p': '逼',  'q': '克由', 'r': '啊爾', 's': '誒斯', 't': '踢',
    'u': '有',  'v': '唯',  'w': '搭不溜', 'x': '伊克斯', 'y': '慰', 'z': '賊',
}

_SAFE_PUNCT = set('，。！？、；：「」『』【】《》…—～')


def preprocess_for_tts(text: str) -> str:
    """Clean LLM output for TTS: strip Markdown, transliterate English, filter rare chars."""
    # 1. Strip Markdown formatting
    text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.*?\)', r'\1', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

    # 2. Transliterate English letters to Mandarin phonetics
    text = re.sub(r'[A-Za-z]+', lambda m: ''.join(
        _EN_LETTER_ZH.get(c.lower(), '') for c in m.group()
    ), text)

    # 3. Filter rare / unsupported characters (keep CJK, kana, safe punctuation, digits)
    filtered = []
    for c in text:
        cp = ord(c)
        if (0x4E00 <= cp <= 0x9FFF or   # CJK Unified Ideographs
                0x3400 <= cp <= 0x4DBF or   # CJK Extension A
                0xF900 <= cp <= 0xFAFF or   # CJK Compatibility
                0x3040 <= cp <= 0x30FF or   # Hiragana + Katakana
                c in _SAFE_PUNCT or
                c.isdigit()):
            filtered.append(c)
        else:
            filtered.append('，')
    text = ''.join(filtered)

    # 4. Collapse repeated punctuation and trim leading commas
    text = re.sub(r'[，。！？]{2,}', '。', text)
    text = text.strip('，')

    return text
