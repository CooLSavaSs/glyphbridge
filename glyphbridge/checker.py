"""Meaning checker ("çeviri denetçisi").

It does not translate. It embeds the source sentence and the translation with a
multilingual sentence encoder (LaBSE, 109 languages) and compares their meaning.
If the similarity is below the threshold the router sends the sentence to the next
backend; if no backend passes, the best attempt is returned with ``flagged=True``
so the user can see it next to the original.

Sentence similarity alone misses errors that keep the overall meaning close: a wrong
number, a dropped or changed name. So the checker also runs two cheap, model-free
consistency checks (``consistency``):

* every number in the source must appear in the translation;
* names (capitalised words inside a Latin-script sentence) must survive when both
  sides use the Latin script.
"""

from __future__ import annotations

import os
import re
import unicodedata
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
        from .cards import CARDS
        revision = CARDS["checker"].revision if MODEL_ID == CARDS["checker"].repo else None
        return SentenceTransformer(MODEL_ID, device="cpu", revision=revision)
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


# -- model-free consistency checks ---------------------------------------------
_NUM = re.compile(r"\d+(?:[.,\u00a0 ]\d{3})*(?:[.,]\d+)?")
_WORD = re.compile(r"[^\W\d_][\w'’-]*", re.UNICODE)


def _numbers(text: str) -> List[str]:
    out = []
    for m in _NUM.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if digits:
            out.append(digits.lstrip("0") or "0")
    return out


def _is_latin(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum("LATIN" in unicodedata.name(c, "") for c in letters) / len(letters) > 0.8


def _names(text: str) -> List[str]:
    """Capitalised words that are not the first word of a sentence."""
    names, start = [], True
    for m in _WORD.finditer(text):
        word = m.group()
        before = text[:m.start()].rstrip()
        start = not before or before[-1] in ".!?:;\"“«("
        if not start and word[0].isupper() and len(word) >= 3:
            names.append(re.split(r"['’]", word)[0])   # Ahmet'in -> Ahmet
    return names


def consistency(source: str, translation: str) -> List[str]:
    """Problems that sentence similarity cannot see. Empty list = no problem found."""
    problems = []
    have = _numbers(translation)
    for n in _numbers(source):
        if n in have:
            have.remove(n)
        else:
            problems.append(f"number {n} missing")
    if _is_latin(source) and _is_latin(translation):
        low = translation.lower()
        for name in _names(source):
            stem = name.lower()[: max(3, len(name) - 2)]   # allow small suffix changes
            if stem not in low:
                problems.append(f"name {name} missing")
    return problems
