"""Glossary: keep terms consistent across a whole document.

A translation memory (``memory.py``) pins whole sentences. A glossary pins *terms*
inside any sentence: wherever the source term appears, its fixed translation must
appear in the output. A sentence that breaks the glossary goes to the next card; if
none follows it, the sentence is flagged for review with the term it missed.

    # source_lang<TAB>target_lang<TAB>term<TAB>translation
    tr	en	Belediye	Municipality
    tr	en	vakıf	foundation

Point GLYPHBRIDGE_GLOSSARY at one or more files (OS path separator), or pass
``--glossary`` on the command line. Matching ignores case and accepts suffixes after
the term (``Belediye'ye``, ``vakıflar``, ``foundations``), because Turkish and many other
languages attach endings to words.
"""

from __future__ import annotations

import os
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

_WORD = re.compile(r"\w+", re.UNICODE)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    # Turkish dotted/dotless I fold to the same letter, so "İstanbul" matches "istanbul".
    return text.replace("İ", "i").replace("I", "ı").casefold().replace("ı", "i")


def _words(text: str) -> List[str]:
    return _WORD.findall(_fold(text))


def _contains(text_words: List[str], term: str) -> bool:
    """True when the (possibly multi-word) term appears; its last word may carry a suffix."""
    tw = _words(term)
    if not tw:
        return False
    n = len(tw)
    for i in range(len(text_words) - n + 1):
        if text_words[i:i + n - 1] == tw[:-1] and text_words[i + n - 1].startswith(tw[-1]):
            return True
    return False


class Glossary:
    def __init__(self, paths: Optional[List[str]] = None):
        self.paths = [p for p in (paths or []) if p]
        self.terms: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
        for path in self.paths:
            self.load(path)

    @classmethod
    def from_env(cls) -> "Glossary":
        raw = os.environ.get("GLYPHBRIDGE_GLOSSARY", "")
        return cls(raw.split(os.pathsep) if raw else [])

    def load(self, path: str) -> None:
        with open(path, encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                if not line.strip() or line.startswith("#"):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) != 4:
                    raise ValueError(f"{path}:{n}: expected 4 tab-separated columns "
                                     "(source_lang, target_lang, term, translation)")
                src, tgt, term, translation = (p.strip() for p in parts)
                self.terms.setdefault((src.lower(), tgt.lower()), []).append((term, translation))

    def check(self, source_text: str, translation: str, source: str, target: str) -> List[str]:
        """Issues for glossary terms in the source whose fixed translation is missing."""
        entries = self.terms.get((source, target))
        if not entries:
            return []
        src_words, out_words = _words(source_text), _words(translation)
        return [f"glossary: '{term}' should be '{fixed}'" for term, fixed in entries
                if _contains(src_words, term) and not _contains(out_words, fixed)]

    def fingerprint(self) -> tuple:
        out = []
        for p in self.paths:
            try:
                out.append((p, os.path.getmtime(p)))
            except OSError:
                out.append((p, None))
        return tuple(out)

    def __len__(self) -> int:
        return sum(len(v) for v in self.terms.values())
