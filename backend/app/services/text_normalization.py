from __future__ import annotations

import re
import unicodedata


_ZERO_WIDTH = re.compile(r"[\u200b-\u200d\ufeff]")
_NON_TEXT = re.compile(r"[^\w\u0e00-\u0e7f]+", re.UNICODE)


def normalize_text(value: str) -> str:
    """Normalize ASR text while preserving Thai and Latin command words."""
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = _ZERO_WIDTH.sub("", text)
    text = _NON_TEXT.sub(" ", text)
    return " ".join(text.split())


def compact_text(value: str) -> str:
    """Return normalized text without whitespace for Thai no-space phrases."""
    return normalize_text(value).replace(" ", "")
