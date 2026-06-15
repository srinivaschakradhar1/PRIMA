"""Token counting helpers.

Uses ``tiktoken`` when available (accurate for OpenAI models); otherwise falls
back to a fast word/character based approximation. The pipeline only needs token
counts to size parent/child chunks, so an approximation is acceptable offline.
"""

from __future__ import annotations

import functools
import re

_WORD_RE = re.compile(r"\w+|[^\w\s]")


@functools.lru_cache(maxsize=4)
def _encoder(model: str):  # pragma: no cover - depends on optional dep
    import tiktoken

    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Return an estimated token count for ``text``."""
    if not text:
        return 0
    try:  # pragma: no cover - optional dependency
        return len(_encoder(model).encode(text))
    except Exception:
        # Approximation: tokens ~= number of word-ish units, with a small
        # multiplier that empirically tracks tiktoken on English prose.
        words = _WORD_RE.findall(text)
        return max(1, int(len(words) * 1.3))
