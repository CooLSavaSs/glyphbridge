"""Language identification.

Uses GlotLID (1,600+ languages, fastText) when ``fasttext`` and ``huggingface_hub``
are installed, and falls back to ``langdetect`` (55 languages).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

# GlotLID returns ISO 639-3 codes with a script, e.g. "tur_Latn".
# The translation models mostly use ISO 639-1, so map the common ones.
ISO3_TO_1 = {
    "eng": "en", "tur": "tr", "deu": "de", "fra": "fr", "spa": "es", "ita": "it", "por": "pt",
    "rus": "ru", "arb": "ar", "ara": "ar", "cmn": "zh", "zho": "zh", "jpn": "ja", "kor": "ko",
    "hin": "hi", "nld": "nl", "pol": "pl", "ukr": "uk", "pes": "fa", "fas": "fa", "ell": "el",
    "heb": "he", "swe": "sv", "dan": "da", "fin": "fi", "ces": "cs", "ron": "ro", "hun": "hu",
    "bul": "bg", "srp": "sr", "hrv": "hr", "slk": "sk", "slv": "sl", "lit": "lt", "lvs": "lv",
    "ekk": "et", "ind": "id", "zsm": "ms", "vie": "vi", "tha": "th", "ben": "bn", "urd": "ur",
    "tam": "ta", "tel": "te", "mar": "mr", "guj": "gu", "kan": "kn", "mal": "ml", "pan": "pa",
    "swh": "sw", "zul": "zu", "aze": "az", "azj": "az", "kaz": "kk", "uzn": "uz", "kat": "ka",
    "hye": "hy", "lat": "la", "cat": "ca", "glg": "gl", "eus": "eu", "cym": "cy", "gle": "ga",
    "isl": "is", "mkd": "mk", "sqi": "sq", "als": "sq", "bel": "be", "nob": "no", "nno": "nn",
    "kmr": "ku", "ckb": "ckb", "tgl": "tl", "amh": "am", "som": "so", "hau": "ha", "yor": "yo",
    "ibo": "ig", "khm": "km", "lao": "lo", "mya": "my", "sin": "si", "npi": "ne", "mon": "mn",
}


@lru_cache(maxsize=1)
def _glotlid():
    try:
        import fasttext  # type: ignore
        from huggingface_hub import hf_hub_download  # type: ignore
    except ImportError:
        return None
    try:
        path = hf_hub_download(repo_id="cis-lmu/glotlid", filename="model.bin")
        return fasttext.load_model(path)
    except Exception:  # offline, blocked, corrupt download...
        return None


def detect(text: str) -> Optional[str]:
    """Return a language code (ISO 639-1 where one exists), or None."""
    sample = " ".join(text.split())[:1000]
    if not sample:
        return None
    model = _glotlid()
    if model is not None:
        try:
            label = model.predict(sample)[0][0]
        except ValueError:
            # fastText's Python wrapper breaks with NumPy 2 ("Unable to avoid copy");
            # its C++ predictor works, so call it directly.
            label = model.f.predict(sample, 1, 0.0, "strict")[0][1]
        code = label.replace("__label__", "").split("_")[0]
        return ISO3_TO_1.get(code, code)
    try:
        from langdetect import detect as ld  # type: ignore
        return ld(sample).split("-")[0]
    except Exception:
        return None
