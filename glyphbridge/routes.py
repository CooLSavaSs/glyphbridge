"""Measured route table: which card goes first for a language pair.

The fixed order in ``backends.default_backends`` is the fallback. For the pairs below,
the cards that scored best on golden-v2 (CI #96/#97, chrF) are tried first, in this
order; cards that are not installed are simply skipped, and every other card still
follows as a fallback. Change an entry only together with new golden-set numbers.
``GLYPHBRIDGE_ROUTES=0`` turns the table off.
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

# pair -> (cards, best first; evidence)
ROUTES: Dict[str, Tuple[List[str], str]] = {
    "tr-en": (["opus", "hymt2-q4", "gemma-q4"], "opus 73.2 > hymt2-q4 70.6 > gemma-q4 69.0"),
    "en-tr": (["opus", "hymt2-q4", "gemma-q4"], "opus 76.8 = hymt2-q4 76.8 > gemma-q4 68.7; opus is smaller"),
    "de-en": (["opus", "hymt2-q4"], "opus 85.6 > hymt2-q4 80.1"),
    "fr-en": (["opus", "hymt2-q4"], "opus 80.1 > hymt2-q4 76.5"),
    "es-en": (["hymt2-q4", "opus"], "hymt2-q4 88.9 > opus 86.9"),
    "ru-en": (["hymt2-q4", "opus"], "hymt2-q4 80.8 > opus 74.8"),
    "ar-en": (["hymt2-q4", "opus"], "hymt2-q4 90.5 > opus 76.4"),
    "zh-en": (["hymt2-q4", "opus"], "hymt2-q4 86.5 > opus 58.3"),
    "la-en": (["gemma-q4", "gemma", "opus-group", "madlad-int8"], "gemma-q4 75.1 > opus-group 49.5"),
}

VERSION = "golden-v2-ci96"


def enabled() -> bool:
    return os.environ.get("GLYPHBRIDGE_ROUTES", "1") != "0"


def preferred(source: str, target: str) -> List[str]:
    """Card names to try first for this pair, best first (empty if not measured)."""
    if not enabled():
        return []
    entry = ROUTES.get(f"{source}-{target}")
    return list(entry[0]) if entry else []


def rank(names: List[str], source: str, target: str) -> List[int]:
    """Sort keys that put measured-best cards first and keep the default order otherwise."""
    pref = preferred(source, target)
    return [pref.index(n) if n in pref else len(pref) + i for i, n in enumerate(names)]
