import re

# The emotions the role card is allowed to tag, matching CharacterState /
# the Live2D expression set the frontend understands.
EMOTIONS = {"neutral", "happy", "angry", "sad", "surprised", "shy"}

# A leading [emotion] tag: tolerant of half- or full-width brackets and
# surrounding whitespace, e.g. "[happy]…", " ［surprised］ …".
_LEADING_TAG_RE = re.compile(r"^\s*[\[［]\s*([A-Za-z]+)\s*[\]］]\s*")


def parse_emotion_tag(text: str) -> tuple[str, str]:
    """Split a ``[emotion]spoken text`` reply into ``(emotion, reply_text)``.

    The streaming format drops JSON in favour of a leading emotion tag.  This
    is deliberately forgiving so a small local model can't easily break it:

    - no tag, or an unrecognised emotion → ``("neutral", <text unchanged>)``
    - a recognised tag → that emotion, with the tag stripped from the text

    Never raises; callers can always trust they get a valid emotion and the
    spoken text with any leading tag removed.
    """
    if not text:
        return "neutral", ""

    match = _LEADING_TAG_RE.match(text)
    if match:
        emotion = match.group(1).lower()
        if emotion in EMOTIONS:
            return emotion, text[match.end():]
        # Recognised-shape tag but unknown emotion: still strip it, stay neutral.
        return "neutral", text[match.end():]

    return "neutral", text


def try_resolve_emotion_prefix(
    buffer: str, max_wait: int = 16
) -> tuple[str, str] | None:
    """Streaming variant: decide the leading emotion from a *partial* buffer.

    Returns ``(emotion, remaining_text)`` once the leading tag is resolved, or
    ``None`` meaning "keep buffering — the tag may still be arriving".

    Resolution rules:
    - only whitespace so far → ``None`` (wait)
    - first non-space char isn't a bracket → no tag, ``("neutral", buffer)``
    - a complete ``[emotion]`` tag is present → parse it
    - a bracket opened but no ``]`` after ``max_wait`` chars → give up, treat the
      whole thing as text (``"neutral"``)
    """
    stripped = buffer.lstrip()
    if not stripped:
        return None
    if stripped[0] not in "[［":
        return "neutral", buffer
    if _LEADING_TAG_RE.match(buffer):
        return parse_emotion_tag(buffer)
    if len(buffer) >= max_wait:
        return "neutral", buffer
    return None
