"""Emotion module: keeps the tone of a sentence through translation.

A small multilingual sentiment model (DistilBERT, 135M parameters, Apache 2.0) reads
the source and the translation and labels each positive, neutral or negative. When a
clearly positive sentence comes back clearly negative (or the other way round), the
translation is flagged with an issue, and the router tries the next card.

It is a card like the others: off until installed (``glyphbridge cards install emotion``)
or ``GLYPHBRIDGE_EMOTION=1``; loaded only when a translation is checked; about 0.6 GB RAM.
Turn it off with ``GLYPHBRIDGE_EMOTION=0``.
"""

from __future__ import annotations

import os
from typing import List, Optional, Sequence, Tuple

from . import cards

Label = Optional[Tuple[str, float]]   # ("positive" | "neutral" | "negative", score)
OPPOSITE = {"positive": "negative", "negative": "positive"}


class Emotion:
    card = "emotion"

    def __init__(self, min_score: float = 0.6):
        self.min_score = min_score
        self._pipe = None
        self._failed = False

    def enabled(self) -> bool:
        flag = os.environ.get("GLYPHBRIDGE_EMOTION")
        if flag == "0" or self._failed:
            return False
        return flag == "1" or cards.is_installed(cards.CARDS[self.card].repo)

    def _load(self):
        if self._pipe is None:
            try:
                from transformers import pipeline  # type: ignore
                c = cards.CARDS[self.card]
                self._pipe = pipeline("text-classification", model=c.repo, revision=c.revision,
                                      device=-1, truncation=True)
            except Exception:  # noqa: BLE001 - no transformers, offline, ...: the module just stays off
                self._failed = True
                return None
        return self._pipe

    def labels(self, texts: Sequence[str]) -> List[Label]:
        if not self.enabled() or not texts:
            return [None] * len(texts)
        pipe = self._load()
        if pipe is None:
            return [None] * len(texts)
        return [(r["label"].lower(), float(r["score"])) for r in pipe(list(texts))]

    def flipped(self, source: Label, translation: Label) -> Optional[str]:
        """An issue text when a clear tone turned into its opposite, else None."""
        if not source or not translation:
            return None
        (s, sp), (t, tp) = source, translation
        if OPPOSITE.get(s) == t and sp >= self.min_score and tp >= self.min_score:
            return f"tone changed: {s} -> {t}"
        return None
