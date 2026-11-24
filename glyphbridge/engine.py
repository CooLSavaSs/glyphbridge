"""Translation router.

For every sentence:

1. **Detect** the source language (GlotLID) unless it is given.
2. **Route** to the first backend that supports the pair: Opus-MT direct model ->
   TranslateGemma (if enabled) -> MADLAD-400. If no backend supports the pair
   directly, pivot through English.
3. **Check** the meaning of each translation against its source (LaBSE). Sentences
   that fail go to the next backend; the best attempt wins. If none passes, the
   result is returned with ``flagged=True`` (shown as a warning by the CLI).
   Numbers and names are also checked without any model (``checker.consistency``).

``confidence`` is the checker's similarity when the checker is installed,
otherwise the model's own token probability (None when the backend gives none).
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass, field, replace
from typing import Dict, List, Optional, Sequence

import logging
import os
import unicodedata

from . import cards, lid
from .backends import Backend, BackendUnavailable, default_backends
from .checker import Checker, consistency

log = logging.getLogger("glyphbridge")

PIVOT = "en"

# Core languages listed by ``glyphbridge languages``. Many more work through MADLAD-400.
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "en": "English", "tr": "Turkish", "de": "German", "fr": "French", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "ru": "Russian", "ar": "Arabic", "zh": "Chinese",
    "ja": "Japanese", "ko": "Korean", "hi": "Hindi", "nl": "Dutch", "pl": "Polish",
    "uk": "Ukrainian", "fa": "Persian", "el": "Greek", "he": "Hebrew", "sv": "Swedish",
    "id": "Indonesian", "vi": "Vietnamese", "th": "Thai", "bn": "Bengali", "ur": "Urdu",
    "sw": "Swahili", "az": "Azerbaijani", "kk": "Kazakh", "uz": "Uzbek", "ka": "Georgian",
    "la": "Latin", "ku": "Kurdish",
}


class TranslationError(RuntimeError):
    """Raised when a translation cannot be produced."""


@dataclass
class TranslationResult:
    translation: str
    source: str
    target: str
    confidence: Optional[float]
    model: str
    flagged: bool = False
    similarity: Optional[float] = None
    attempts: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class Engine:
    def __init__(self, backends: Optional[List[Backend]] = None, checker: Optional[Checker] = None):
        if cards.offline():
            os.environ["HF_HUB_OFFLINE"] = "1"  # use installed cards only, never download
        self.backends = backends if backends is not None else default_backends()
        self.checker = checker if checker is not None else Checker()
        # Results cache: a sentence repeated in a document is translated only once.
        self._cache: "OrderedDict[tuple, TranslationResult]" = OrderedDict()
        self.cache_size = int(os.environ.get("GLYPHBRIDGE_RESULT_CACHE", "2048"))

    def fingerprint(self) -> tuple:
        """Everything that can change a translation besides the text and languages:
        which cards are in use (and their pinned revisions), the routing preference
        and the checker threshold. Part of the cache key, so a result from one model,
        model version or setting is never reused for another."""
        cards_used = tuple((b.name, getattr(b, "revision", None) or getattr(b, "repo", None)
                            or getattr(b, "model_id", None)) for b in self.backends)
        return (cards_used, os.environ.get("GLYPHBRIDGE_PREFER", "speed"),
                getattr(self.checker, "threshold", None), cards.ram_budget_mb())

    def _ordered(self) -> List[Backend]:
        """Backends in the order to try them.

        * ``GLYPHBRIDGE_PREFER=quality`` tries TranslateGemma before the fast Opus-MT models.
        * Cards whose estimated RAM does not fit the current RAM budget move to the end,
          so a small card is tried before a large one would push the PC into swap.
        """
        order = list(self.backends)
        if os.environ.get("GLYPHBRIDGE_PREFER", "speed") == "quality":
            order.sort(key=lambda b: 0 if b.name.startswith("gemma") else 1)
        budget = cards.ram_budget_mb()
        return sorted(order, key=lambda b: 1 if getattr(b, "ram_mb", 0) > budget else 0)

    def candidates(self, source: str, target: str) -> List[list]:
        """Routes to try, best first. A route is a list of (backend, src, tgt) hops."""
        backends = self._ordered()

        def ok(b, src, tgt):
            # One broken card must not take the whole translation down.
            try:
                return b.supports(src, tgt)
            except Exception as exc:  # noqa: BLE001
                log.warning("backend %s failed on %s-%s: %s", b.name, src, tgt, exc)
                return False

        routes = [[(b, source, target)] for b in backends if ok(b, source, target)]
        if PIVOT not in (source, target):
            first = next((b for b in backends if ok(b, source, PIVOT)), None)
            second = next((b for b in backends if ok(b, PIVOT, target)), None)
            if first and second:
                routes.append([(first, source, PIVOT), (second, PIVOT, target)])
        return routes

    def _run_route(self, route, texts: Sequence[str]):
        current, probs = list(texts), [1.0] * len(texts)
        for backend, src, tgt in route:
            out = backend.translate(current, src, tgt)
            current = [t for t, _ in out]
            probs = [None if p is None or q is None else p * q for p, (_, q) in zip(probs, out)]
        label = " -> ".join(f"{b.name}:{s}-{t}" for b, s, t in route)
        return current, probs, label

    def translate_batch(self, texts: Sequence[str], target: str, source: str = "auto") -> List[TranslationResult]:
        """Translate texts, reusing cached results and translating each distinct text once."""
        if not texts:
            return []
        if source in (None, "", "auto"):
            detected = lid.detect(" ".join(texts))
            if not detected:
                raise TranslationError("Could not detect the source language; pass source=...")
            source = detected
        source, target = source.lower(), target.lower()
        fp = self.fingerprint()
        keys = [(_normalize(t), source, target, fp) for t in texts]
        todo = list(dict.fromkeys(k for k in keys if k not in self._cache))
        if todo:
            first_text = {}
            for t, k in zip(texts, keys):
                first_text.setdefault(k, t)
            fresh = self._translate_uncached([first_text[k] for k in todo], target, source)
            for k, r in zip(todo, fresh):
                self._cache[k] = r
                self._cache.move_to_end(k)
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        return [replace(self._cache[k], attempts=list(self._cache[k].attempts)) for k in keys]

    def _translate_uncached(self, texts: Sequence[str], target: str, source: str) -> List[TranslationResult]:
        if not texts:
            return []
        target = target.lower()
        if source in (None, "", "auto"):
            detected = lid.detect(" ".join(texts))
            if not detected:
                raise TranslationError("Could not detect the source language; pass source=...")
            source = detected
        source = source.lower()
        if source == target:
            return [TranslationResult(t, source, target, 1.0, "identity") for t in texts]

        routes = self.candidates(source, target)
        if not routes:
            raise TranslationError(f"Language pair not supported yet: {source} -> {target}")

        best: List[Optional[TranslationResult]] = [None] * len(texts)
        pending = list(range(len(texts)))
        for route in routes:
            if not pending:
                break
            try:
                outs, probs, label = self._run_route(route, [texts[i] for i in pending])
            except BackendUnavailable:
                continue
            sims = self.checker.similarity([texts[i] for i in pending], outs)
            still = []
            for i, out, prob, sim in zip(pending, outs, probs, sims):
                conf = sim if sim is not None else prob
                issues = consistency(texts[i], out)
                ok = self.checker.passes(sim) and not issues
                prev = best[i]
                attempts = (prev.attempts if prev else []) + [label]
                cand = TranslationResult(out, source, target, None if conf is None else round(conf, 4), label,
                                         flagged=not ok, similarity=sim, attempts=attempts, issues=issues)
                better = (len(cand.issues), -(cand.confidence or 0)) < (len(prev.issues), -(prev.confidence or 0)) if prev else True
                if prev is None or ok or better:
                    best[i] = cand
                else:
                    prev.attempts = attempts
                if not ok:
                    still.append(i)
            pending = still

        if any(r is None for r in best):
            raise TranslationError(f"No backend could translate {source} -> {target} (models unavailable?)")
        return best  # type: ignore[return-value]

    def translate(self, text: str, target: str, source: str = "auto") -> TranslationResult:
        return self.translate_batch([text], target=target, source=source)[0]


def _normalize(text: str) -> str:
    """Cache-key form of a text: Unicode NFC, whitespace collapsed."""
    return " ".join(unicodedata.normalize("NFC", text).split())


_default: Optional[Engine] = None


def get_engine() -> Engine:
    global _default
    if _default is None:
        _default = Engine()
    return _default


def translate(text: str, to: str, source: str = "auto") -> TranslationResult:
    """Translate ``text`` into the language ``to``.

    >>> import glyphbridge
    >>> glyphbridge.translate("Merhaba dünya", to="en", source="tr").translation
    'Hello world'
    """
    return get_engine().translate(text, target=to, source=source)
