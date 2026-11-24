"""Translation memory: your own fixed translations, used before any model.

Idioms, product names and house terms are where machine translation goes wrong most
often (golden-v1: idioms chrF 18-38). A memory file pins how a whole sentence or
expression is translated:

    # source_lang<TAB>target_lang<TAB>source<TAB>translation
    tr	en	Gözden ırak olan gönülden de ırak olur.	Out of sight, out of mind.
    en	tr	It's raining cats and dogs.	Bardaktan boşanırcasına yağmur yağıyor.

Point GLYPHBRIDGE_MEMORY at one or more such files (separated by the OS path
separator), or pass ``--memory`` on the command line. Matching ignores case, extra
spaces and the final punctuation mark. Glyphbridge ships no built-in memory: the
entries are yours.
"""

from __future__ import annotations

import os
import unicodedata
from typing import Dict, List, Optional, Tuple

Key = Tuple[str, str, str]


def _key(text: str) -> str:
    text = " ".join(unicodedata.normalize("NFC", text).split()).casefold()
    return text.rstrip(".!?。！？…")


class Memory:
    def __init__(self, paths: Optional[List[str]] = None):
        self.paths = [p for p in (paths or []) if p]
        self.entries: Dict[Key, str] = {}
        for path in self.paths:
            self.load(path)

    @classmethod
    def from_env(cls) -> "Memory":
        raw = os.environ.get("GLYPHBRIDGE_MEMORY", "")
        return cls(raw.split(os.pathsep) if raw else [])

    def load(self, path: str) -> None:
        with open(path, encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                if not line.strip() or line.startswith("#"):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) != 4:
                    raise ValueError(f"{path}:{n}: expected 4 tab-separated columns "
                                     "(source_lang, target_lang, source, translation)")
                src, tgt, text, translation = parts
                self.entries[(src.strip().lower(), tgt.strip().lower(), _key(text))] = translation.strip()

    def get(self, text: str, source: str, target: str) -> Optional[str]:
        return self.entries.get((source, target, _key(text)))

    def fingerprint(self) -> tuple:
        """Files and their modification times, so editing a memory file clears stale cache hits."""
        out = []
        for p in self.paths:
            try:
                out.append((p, os.path.getmtime(p)))
            except OSError:
                out.append((p, None))
        return tuple(out)

    def __len__(self) -> int:
        return len(self.entries)
