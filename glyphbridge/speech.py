"""Speech translation (v0.3 preview): speech -> text -> translation -> speech.

* Speech-to-text: OpenAI Whisper (MIT) through Transformers, the ``whisper`` card.
  Reading audio files needs the ``ffmpeg`` program.
* Text-to-speech: the ``espeak-ng`` program (100+ languages, fully offline).
  Natural-sounding Piper voices are planned as cards.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from typing import List, Optional, Tuple

from .cards import CARDS
from .engine import TranslationResult, get_engine

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".opus", ".webm"}


@lru_cache(maxsize=1)
def _asr():
    try:
        from transformers import pipeline  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Speech needs: pip install glyphbridge (transformers) and ffmpeg") from exc
    return pipeline("automatic-speech-recognition", model=CARDS["whisper"].repo, device="cpu")


def transcribe(path: str, source: str = "auto") -> str:
    """Return the text spoken in an audio file."""
    kwargs = {"return_timestamps": True}
    if source not in (None, "", "auto"):
        kwargs["generate_kwargs"] = {"language": source, "task": "transcribe"}
    result = _asr()(path, **kwargs)
    return result["text"].strip()


def speak(text: str, lang: str, out_wav: str) -> str:
    """Write ``text`` as speech in language ``lang`` to ``out_wav`` with espeak-ng."""
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError("Text-to-speech needs the espeak-ng program (apt install espeak-ng / brew install espeak-ng)")
    subprocess.run([exe, "-v", lang, "-w", out_wav, text], check=True, capture_output=True)
    return out_wav


def translate_audio(path: str, target: str, source: str = "auto", out: Optional[str] = None,
                    speak_out: Optional[str] = None) -> Tuple[str, List[TranslationResult]]:
    """Transcribe ``path``, translate the transcript sentence by sentence and write it
    to ``out`` (default ``name.<target>.txt``). With ``speak_out`` also write speech."""
    text = transcribe(path, source)
    sentences = [s.strip() for s in _split_sentences(text) if s.strip()]
    results = get_engine().translate_batch(sentences, target=target, source=source) if sentences else []
    translation = " ".join(r.translation for r in results)
    stem = os.path.splitext(path)[0]
    out = out or f"{stem}.{target}.txt"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(f"# original\n{text}\n\n# {target}\n{translation}\n")
    if speak_out:
        speak(translation, target, speak_out)
    return out, results


def _split_sentences(text: str) -> List[str]:
    parts, cur = [], ""
    for ch in text:
        cur += ch
        if ch in ".!?。！？؟":
            parts.append(cur)
            cur = ""
    if cur.strip():
        parts.append(cur)
    return parts
