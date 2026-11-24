"""Model cards ("kartlar").

Every model Glyphbridge can use is a *card*. You install only the cards you need
on disk; at run time only the card a sentence actually needs is loaded into RAM,
and cards are unloaded again when the RAM budget is full. Nothing else runs.

    glyphbridge cards                     # list cards, installed or not
    glyphbridge cards install opus:tr-en  # a small, fast card for one language pair
    glyphbridge cards install madlad      # rare languages (400+)
    glyphbridge cards remove madlad

RAM and disk figures are estimates for CPU use (weights × bytes per weight), not
measurements; real use is usually somewhat higher.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Card:
    id: str
    title: str
    repo: str
    ram_mb: int
    disk: str
    license: str
    note: str = ""


CARDS: Dict[str, Card] = {
    "madlad": Card("madlad", "MADLAD-400 3B — 400+ languages, rare languages",
                   "google/madlad400-3b-mt", 6500, "~12 GB", "Apache-2.0",
                   "Loaded in bfloat16. An int8 card (~3 GB RAM) is planned."),
    "gemma": Card("gemma", "TranslateGemma 4B — highest quality, ~55 languages, images",
                  "google/translategemma-4b-it", 9000, "~8.6 GB", "Gemma terms",
                  "Gated: accept the terms on Hugging Face and log in first. "
                  "Needs ~16 GB RAM today; a 4-bit GGUF card for 8 GB PCs is planned."),
    "lid": Card("lid", "GlotLID — language identification, 1,600+ languages",
                "cis-lmu/glotlid", 500, "?", "Apache-2.0", "Size not measured yet."),
    "checker": Card("checker", "LaBSE — meaning checker, 109 languages",
                    "sentence-transformers/LaBSE", 1000, "~1.9 GB", "Apache-2.0"),
    "whisper": Card("whisper", "Whisper small — speech to text, ~99 languages",
                    "openai/whisper-small", 1000, "~1 GB", "MIT", "Reading audio files needs ffmpeg."),
}

OPUS_PREFIX = "opus:"
OPUS_RAM_MB = 600


def opus_repos(pair: str) -> List[str]:
    src, tgt = pair.split("-", 1)
    return [f"Helsinki-NLP/opus-mt-tc-big-{src}-{tgt}", f"Helsinki-NLP/opus-mt-{src}-{tgt}"]


def resolve(card_id: str) -> Card:
    if card_id.startswith(OPUS_PREFIX):
        pair = card_id[len(OPUS_PREFIX):]
        return Card(card_id, f"Opus-MT {pair} — small and fast", opus_repos(pair)[0],
                    OPUS_RAM_MB, "~300 MB", "CC-BY-4.0", "Falls back to the base model if no tc-big model exists.")
    if card_id not in CARDS:
        raise KeyError(f"Unknown card: {card_id}. Try: {', '.join(CARDS)} or opus:<src>-<tgt>")
    return CARDS[card_id]


# -- what is on disk -----------------------------------------------------------
def _cached_repos() -> set:
    try:
        from huggingface_hub import scan_cache_dir  # type: ignore
        return {r.repo_id for r in scan_cache_dir().repos}
    except Exception:
        return set()


def is_installed(repo: str, cached: Optional[set] = None) -> bool:
    return repo in (cached if cached is not None else _cached_repos())


def installed_cards() -> List[str]:
    cached = _cached_repos()
    found = [c.id for c in CARDS.values() if c.repo in cached]
    for repo in sorted(cached):
        for prefix in ("Helsinki-NLP/opus-mt-tc-big-", "Helsinki-NLP/opus-mt-"):
            if repo.startswith(prefix):
                found.append(OPUS_PREFIX + repo[len(prefix):])
                break
    return found


def install(card_id: str) -> str:
    from huggingface_hub import snapshot_download  # type: ignore
    if card_id.startswith(OPUS_PREFIX):
        last = None
        for repo in opus_repos(card_id[len(OPUS_PREFIX):]):
            try:
                return snapshot_download(repo)
            except Exception as exc:  # try the base model next
                last = exc
        raise RuntimeError(f"No Opus-MT model for {card_id}: {last}")
    return snapshot_download(resolve(card_id).repo)


def remove(card_id: str) -> int:
    from huggingface_hub import scan_cache_dir  # type: ignore
    repos = opus_repos(card_id[len(OPUS_PREFIX):]) if card_id.startswith(OPUS_PREFIX) else [resolve(card_id).repo]
    info = scan_cache_dir()
    revisions = [rev.commit_hash for r in info.repos if r.repo_id in repos for rev in r.revisions]
    if not revisions:
        return 0
    strategy = info.delete_revisions(*revisions)
    freed = strategy.expected_freed_size
    strategy.execute()
    return freed


# -- RAM budget ------------------------------------------------------------------
def ram_budget_mb() -> int:
    """GLYPHBRIDGE_RAM_BUDGET_MB, else 60% of the RAM that is free right now, else 4 GB."""
    env = os.environ.get("GLYPHBRIDGE_RAM_BUDGET_MB")
    if env:
        return int(env)
    try:
        import psutil  # type: ignore
        return int(psutil.virtual_memory().available / 1024 / 1024 * 0.6)
    except Exception:
        return 4096


def offline() -> bool:
    """With GLYPHBRIDGE_OFFLINE=1 only installed cards are used and nothing is downloaded."""
    return os.environ.get("GLYPHBRIDGE_OFFLINE") == "1"
