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
    # golden-v3 (CI #102)
    "en-de": (["opus", "hymt2-q4"], "opus 88.7 > hymt2-q4 80.1"),
    "en-fr": (["opus", "hymt2-q4"], "opus 96.3 > hymt2-q4 90.1"),
    "en-es": (["opus", "hymt2-q4"], "opus 86.9 > hymt2-q4 86.3"),
    "en-ar": (["opus", "hymt2-q4"], "opus 81.3 > hymt2-q4 69.4"),
    "en-ru": (["hymt2-q4", "opus"], "hymt2-q4 83.8 > opus 70.8"),
    "en-zh": (["hymt2-q4", "opus"], "hymt2-q4 50.6 > opus 39.0"),
    "fa-en": (["gemma-q4", "hymt2-q4", "madlad-int8"], "gemma-q4 88.0 > hymt2-q4 86.9 > madlad-int8 66.0 (CI #103)"),
    "ja-en": (["hymt2-q4", "opus"], "hymt2-q4 92.5 > opus 81.7"),
    "ko-en": (["madlad-int8", "gemma-q4", "hymt2-q4"],
              "FLORES madlad-int8 58.8 > gemma-q4 57.6 > hymt2-q4 55.7 (golden-v3 had hymt2-q4 84.3 on 9 "
              "hand-written sentences; FLORES human references win)"),
    "hi-en": (["gemma-q4", "hymt2-q4", "opus"], "gemma-q4 88.1 > hymt2-q4 78.1 > opus 66.7 (CI #103)"),
    "sw-en": (["gemma-q4", "madlad-int8"], "gemma-q4 92.0 > madlad-int8 70.7; no Opus-MT, no Hy-MT2 (CI #103)"),
    "el-en": (["gemma-q4", "madlad-int8"], "gemma-q4 86.7 > madlad-int8 79.2; Opus tc-big broken (CI #103)"),
    # FLORES-200 devtest, 20 sentences, X->en (runs 45531772163 / 45539184900 / 45539189069).
    # A card moves ahead only when it beats the current first card by >= 3 chrF.
    "bo-en": (["madlad-int8", "hymt2-q4"], "FLORES madlad-int8 38.8 > hymt2-q4 32.2"),
    "mn-en": (["madlad-int8", "hymt2-q4"], "FLORES madlad-int8 58.5 > hymt2-q4 32.5"),
    "kk-en": (["madlad-int8", "hymt2-q4"], "FLORES madlad-int8 59.1 > hymt2-q4 42.9"),
    "ug-en": (["madlad-int8", "hymt2-q4"], "FLORES madlad-int8 54.0 > hymt2-q4 47.5"),
    "ta-en": (["madlad-int8", "gemma-q4", "hymt2-q4"], "FLORES madlad-int8 60.1 > gemma-q4 56.3 > hymt2-q4 54.1"),
    "te-en": (["madlad-int8", "gemma-q4", "hymt2-q4"], "FLORES madlad-int8 64.4 > gemma-q4 58.6 > hymt2-q4 57.2"),
    "km-en": (["madlad-int8", "hymt2-q4"], "FLORES madlad-int8 64.0 > hymt2-q4 59.9"),
    "zu-en": (["madlad-int8", "gemma-q4"], "FLORES madlad-int8 61.7 > gemma-q4 45.3"),
    "ur-en": (["madlad-int8", "gemma-q4", "hymt2-q4"], "FLORES madlad-int8 63.2 > gemma-q4 59.7 > chain 58.3"),
}

VERSION = "flores-v1"


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
