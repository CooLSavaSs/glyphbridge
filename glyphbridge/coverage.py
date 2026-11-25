"""Which languages the installed cards can translate (``glyphbridge languages --all``).

Each card reports its own language list:

* Opus-MT pair cards: the language codes in the names of the installed pair models.
* Hy-MT2 and TranslateGemma: their published language lists.
* MADLAD-400: the ``<2xx>`` target tags in the installed model's SentencePiece vocabulary
  (400+ languages), so the list is exactly what the model on disk knows.

A language counts as covered when at least one installed card handles it.
"""

from __future__ import annotations

import glob
import os
import re
from typing import Dict, List, Optional, Set

from .cards import CARDS, _cached_repos

_OPUS = re.compile(r"^Helsinki-NLP/opus-mt-(?:tc-big-)?([a-z]{2,3})-([a-z]{2,3})$")


def _madlad_tags(repo: str) -> Optional[Set[str]]:
    """Language codes from <2xx> tags in an installed MADLAD SentencePiece model."""
    try:
        from huggingface_hub import scan_cache_dir  # type: ignore
        import sentencepiece as spm  # type: ignore
    except ImportError:
        return None
    for r in scan_cache_dir().repos:
        if r.repo_id != repo:
            continue
        for rev in r.revisions:
            for path in glob.glob(os.path.join(str(rev.snapshot_path), "*.model")):
                sp = spm.SentencePieceProcessor(model_file=path)
                tags = {sp.id_to_piece(i)[2:-1] for i in range(sp.get_piece_size())
                        if re.fullmatch(r"<2[a-zA-Z_-]+>", sp.id_to_piece(i))}
                if tags:
                    return tags
    return None


def by_card(cached: Optional[Set[str]] = None) -> Dict[str, Set[str]]:
    """Installed card id -> language codes it handles."""
    from .backends import GEMMA_DEFAULT_LANGS, HYMT2_LANGS
    cached = _cached_repos() if cached is None else cached
    out: Dict[str, Set[str]] = {}
    opus = set()
    for repo in cached:
        m = _OPUS.match(repo)
        if m:
            opus.update(m.groups())
    if opus:
        out["opus"] = opus
    if CARDS["hymt2-q4"].repo in cached:
        out["hymt2-q4"] = set(HYMT2_LANGS)
    for cid in ("gemma-q4", "gemma"):
        if CARDS[cid].repo in cached:
            out[cid] = set(GEMMA_DEFAULT_LANGS)
    for cid in ("madlad-int8", "madlad"):
        if CARDS[cid].repo in cached:
            out[cid] = _madlad_tags(CARDS[cid].repo) or set()
    return out


def table(cached: Optional[Set[str]] = None) -> List[tuple]:
    """Sorted rows (code, [cards]) for every covered language."""
    cards = by_card(cached)
    langs: Dict[str, List[str]] = {}
    for cid, codes in cards.items():
        for c in codes:
            langs.setdefault(c, []).append(cid)
    return sorted((c, sorted(v)) for c, v in langs.items())
