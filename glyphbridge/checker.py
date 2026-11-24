"""Meaning checker ("çeviri denetçisi").

It does not translate. It embeds the source sentence and the translation with a
multilingual sentence encoder (LaBSE, 109 languages) and compares their meaning.
If the similarity is below the threshold the router sends the sentence to the next
backend; if no backend passes, the best attempt is returned with ``flagged=True``
so the user can see it next to the original.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional, Sequence

MODEL_ID = os.environ.get("GLYPHBRIDGE_CHECKER_MODEL", "sentence-transformers/LaBSE")
THRESHOLD = float(os.environ.get("GLYPHBRIDGE_CHECK_THRESHOLD", "0.75"))


@lru_cache(maxsize=1)
def _encoder():
    if os.environ.get("GLYPHBRIDGE_DISABLE_CHECKER") == "1":
        return None
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        return SentenceTransformer(MODEL_ID, device="cpu")
    except Exception:
        return None


class Checker:
    def __init__(self, threshold: float = THRESHOLD):
        self.threshold = threshold

    @property
    def available(self) -> bool:
        return _encoder() is not None

    def similarity(self, sources: Sequence[str], translations: Sequence[str]) -> List[Optional[float]]:
        enc = _encoder()
        if enc is None:
            return [None] * len(sources)
        a = enc.encode(list(sources), normalize_embeddings=True)
        b = enc.encode(list(translations), normalize_embeddings=True)
        return [round(float((x * y).sum()), 4) for x, y in zip(a, b)]

    def passes(self, score: Optional[float]) -> bool:
        return score is None or score >= self.threshold
