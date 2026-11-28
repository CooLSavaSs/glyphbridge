"""Model cards ("kartlar").

Every model Glyphbridge can use is a *card*. You install only the cards you need
on disk; at run time only the card a sentence actually needs is loaded into RAM,
and cards are unloaded again when the RAM budget is full. Nothing else runs.

    glyphbridge cards                     # list cards, installed or not
    glyphbridge cards install opus:tr-en  # a small, fast card for one language pair
    glyphbridge cards install madlad      # rare languages (400+)
    glyphbridge cards remove madlad

RAM and disk figures are estimates for CPU use (weights × bytes per weight), not
measurements, unless marked "measured"; real use is usually somewhat higher.

Every non-Opus card is pinned to an exact model revision, and the main weight files
of the community-hosted cards are checked against a pinned SHA-256 after download
(``glyphbridge cards verify``). Opus-MT pair cards come from the official
Helsinki-NLP organisation and follow its latest release.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Card:
    id: str
    title: str
    repo: str
    ram_mb: int
    disk: str
    license: str
    note: str = ""
    # Exact Hugging Face commit to download, so a model cannot change under users'
    # feet (supply-chain safety). Update deliberately, after testing the new version.
    revision: Optional[str] = None
    # SHA-256 of the main weight files at that revision, checked after download.
    sha256: Tuple[Tuple[str, str], ...] = ()


CARDS: Dict[str, Card] = {
    "madlad-int8": Card("madlad-int8", "MADLAD-400 3B int8 — 400+ languages, fits 8 GB PCs",
                        "Nextcloud-AI/madlad400-3b-mt-ct2-int8", 5500, "2.98 GB", "Apache-2.0",
                        "Default rare-language card (CTranslate2). 3.3-5.5 GB peak RAM measured in CI (two runs).",
                    revision="aa32bbdeba7880eff2096ec044cb155a340a9400",
                    sha256=(("model.bin", "77b9fd9ab97c1259d07089b5f854393dad81bc5fb5647d3f9a5d101c94f40daa"),
                            ("spiece.model", "ef11ac9a22c7503492f56d48dce53be20e339b63605983e9f27d2cd0e0f3922c"))),
    "gemma-q4": Card("gemma-q4", "TranslateGemma 4B 4-bit — highest quality, fits 8 GB PCs",
                     "anilb/translategemma-gguf", 4800, "2.49 GB", "Gemma terms",
                     "Community Q4_K_M quantization run with llama.cpp. Installing it turns it on. "
                     "4.6-4.8 GB peak RAM measured in CI.",
                    revision="b4a4747a01c36cadf60238985cd31dc6ea66b760",
                    sha256=(("translategemma-4b-it.Q4_K_M.gguf",
                             "81200d03e843d2ec1ece6eeafe7d13cb6e5211e1fcd336ade55790b683a08330"),)),
    "hymt2-q4": Card("hymt2-q4", "Hy-MT2 1.8B 4-bit — 36 languages, best measured TR<->EN, 2.2 GB",
                     "tencent/Hy-MT2-1.8B-GGUF", 2200, "1.13 GB", "Apache-2.0",
                     "Official Q4_K_M GGUF run with llama.cpp. 2.2 GB peak RAM measured in CI.",
                     revision="a0c709d9fac510f2c807aa3af52872340dc37a4a",
                     sha256=(("Hy-MT2-1.8B-Q4_K_M.gguf",
                              "dc5f44fcf1fa496ee7ad725982c0c8c553a4de00259b53af84c4b89fb0c06699"),)),
    "emotion": Card("emotion", "Emotion module — keeps the tone (positive / neutral / negative)",
                    "lxyuan/distilbert-base-multilingual-cased-sentiments-student", 850, "0.55 GB",
                    "Apache-2.0", "Flags translations whose tone flips, e.g. a kind sentence that turns negative.",
                    revision="cf991100d706c13c0a080c097134c05b7f436c45",
                    sha256=(("model.safetensors",
                             "0ab095b69033944004bb7a6ffcbfc2d77a240dd0f71c27820aa73efa71f664fe"),)),
    "madlad": Card("madlad", "MADLAD-400 3B full size — opt-in, needs ~8 GB free RAM",
                   "google/madlad400-3b-mt", 6500, "11.8 GB", "Apache-2.0",
                   "Loaded in bfloat16 (6.5 GB measured). Prefer madlad-int8 on 8 GB PCs.",
                    revision="fa184c675da0b5c9e1c8694fccd4e12e2d422094"),
    "gemma": Card("gemma", "TranslateGemma 4B full size — gated, images",
                  "google/translategemma-4b-it", 9400, "8.64 GB", "Gemma terms",
                  "Gated: accept the terms on Hugging Face and log in first. Needs ~16 GB RAM; "
                  "use gemma-q4 on 8 GB PCs.",
                    revision="10042cb0e6e7fdce748996a71dc3dc432a4e0c89"),
    "lid": Card("lid", "GlotLID — language identification, 1,600+ languages",
                "cis-lmu/glotlid", 1000, "0.78 GB", "Apache-2.0", "",
                    revision="e9592e0a9bc3b6f2a946de94faaa188d1dd6f522",
                    sha256=(("model.bin", "3b26297652e105cb63acde0fbf5aa228161528b519331e58a7c94ea9fe58474c"),)),
    "checker": Card("checker", "LaBSE — meaning checker, 109 languages",
                    "sentence-transformers/LaBSE", 1000, "1.90 GB", "Apache-2.0",
                    revision="836121a0533e5664b21c7aacc5d22951f2b8b25b"),
    "ota-ocr": Card("ota-ocr", "Azra 1-Mini 0.8B — Ottoman Turkish OCR (Arabic script), line images",
                    "OttomanNLP/Azra-1-Mini-0.8b", 3500, "1.73 GB", "Apache-2.0",
                    "Qwen3.5 vision-language model, needs transformers>=5.14. Reads one text LINE per image; "
                    "glyphbridge cuts pages into lines first. Authors report 80.2% (nesih) / 67.1% (rika) "
                    "character accuracy on their test sets; on the model card's 10 sample lines we "
                    "measured 96.9% / 86.5% (after kaf/ye normalization). RAM is an estimate.",
                    revision="7c1c429e9f3d3bad1d59b6ef802264f694b171be",
                    sha256=(("model.safetensors",
                             "dc497f9ba93f6f47fac82a7eb960cd8e70d810d6abd9615a3d563861d0afe87d"),)),
    "whisper": Card("whisper", "Whisper small — speech to text, ~99 languages",
                    "openai/whisper-small", 1000, "0.97 GB", "MIT", "Reading audio files needs ffmpeg.",
                    revision="973afd24965f72e36ca33b3055d56a652f456b4d"),
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


class ChecksumError(RuntimeError):
    """A downloaded model file does not match its pinned SHA-256."""


def _sha256(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify(card_id: str) -> List[str]:
    """Check the pinned SHA-256 of a card's files (downloading them if needed).
    Returns the files checked; raises ChecksumError on a mismatch."""
    from huggingface_hub import hf_hub_download  # type: ignore
    card = resolve(card_id)
    checked = []
    for filename, expected in card.sha256:
        path = hf_hub_download(card.repo, filename, revision=card.revision)
        actual = _sha256(path)
        if actual != expected:
            raise ChecksumError(f"{card_id}: {filename} has SHA-256 {actual}, expected {expected}. "
                                f"Delete it with 'glyphbridge cards remove {card_id}' and install again.")
        checked.append(filename)
    return checked


def install(card_id: str) -> str:
    from huggingface_hub import snapshot_download  # type: ignore
    if card_id.startswith(OPUS_PREFIX):
        last = None
        for repo in opus_repos(card_id[len(OPUS_PREFIX):]):
            try:
                return snapshot_download(repo, ignore_patterns=OPUS_IGNORE)
            except Exception as exc:  # try the base model next
                last = exc
        raise RuntimeError(f"No Opus-MT model for {card_id}: {last}")
    if card_id in ("gemma-q4", "hymt2-q4"):  # GGUF repos hold several sizes; fetch only ours
        card = resolve(card_id)
        path = snapshot_download(card.repo, allow_patterns=[f for f, _ in card.sha256],
                                 revision=card.revision)
        verify(card_id)
        from . import llama_cpu
        llama_cpu.fix(os.path.join(path, card.sha256[0][0]))  # older CPUs: fetch the right llama.cpp
        return path
    card = resolve(card_id)
    path = snapshot_download(card.repo, revision=card.revision, allow_patterns=ALLOW_PATTERNS.get(card_id),
                             ignore_patterns=IGNORE_PATTERNS.get(card_id))
    verify(card_id)
    return path


# Cards whose repos hold extra files we do not need (banners, sample images).
ALLOW_PATTERNS = {
    "ota-ocr": ["*.json", "*.jinja", "model.safetensors", "README*.md"],
}

# Repos that keep the same weights in several formats or versions; the code loads only
# one of them. Without these lists `cards install` downloaded 6.6 GB for `lid` (0.8 GB
# used), 9.4 GB for `checker` (1.9 GB), 3.9 GB for `whisper` (1 GB), 15.7 GB for
# `madlad` (11.8 GB) and 1.6 GB for `emotion` (0.5 GB) — measured from the Hub file
# list at the pinned revisions. Patterns match from the repo root, so a file of the
# same name in a subfolder (LaBSE's 2_Dense/) is kept.
# Opus-MT repos keep the weights twice (PyTorch + TensorFlow, ~300 MB each; measured on
# opus-mt-yo-en / ig-en: 594 MB -> ~300 MB). The PyTorch copy is the one we load.
OPUS_IGNORE = ["tf_model.h5", "flax_model.msgpack", "rust_model.ot", "*.onnx"]

IGNORE_PATTERNS = {
    "lid": ["model_v*"],                                   # lid.py loads model.bin
    "checker": ["tf_model.h5", "flax_model.msgpack", "onnx/*", "pytorch_model.bin"],
    "whisper": ["tf_model.h5", "flax_model.msgpack", "pytorch_model.bin"],
    "madlad": ["*.gguf"],
    "emotion": ["onnx/*", "pytorch_model.bin"],
}


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


def pinned(card_id: str, env_var: str) -> tuple:
    """(repo, revision) for a card: the pinned default, or an override from env_var
    (an override is the user's own choice, so it is not pinned)."""
    override = os.environ.get(env_var)
    card = CARDS[card_id]
    return (override, None) if override else (card.repo, card.revision)
