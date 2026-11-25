"""Historical scripts, first narrow step (work plan items 19 and 20).

What this does today, honestly:

* **Egyptian hieroglyphs**: Unicode hieroglyph text -> Gardiner sign codes
  (A1, D58, G43, ...), from the Unicode character names. This is sign *listing*, not
  reading or translation, and it needs Unicode input: recognising signs in a photo is
  not built yet.
* **Cuneiform**: Unicode cuneiform text -> conventional sign names (A, ASH, ...).
  Sign names are not a transliteration yet: one sign has several readings, and choosing
  the right one (and then Akkadian -> English) needs a model and experts.

No model and no download: everything comes from Python's own Unicode database.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import List, Optional

_GARDINER = re.compile(r"^EGYPTIAN HIEROGLYPH ([A-Z]{1,2})0*(\d+)([A-Z]*)$")
_CUNEIFORM = re.compile(r"^CUNEIFORM (?:NUMERIC |PUNCTUATION )?SIGN (.+)$")


@dataclass
class Sign:
    char: str
    codepoint: str          # "U+13000"
    script: str             # "Egyp" or "Xsux"
    code: str               # Gardiner code ("A1") or cuneiform sign name ("ASH")
    kind: str = "sign"      # "sign", "number", "punctuation", "control"

    def to_dict(self) -> dict:
        return asdict(self)


def gardiner(ch: str) -> Optional[str]:
    """Gardiner code of one Egyptian hieroglyph (``"𓀀"`` -> ``"A1"``), or None."""
    m = _GARDINER.match(unicodedata.name(ch, ""))
    return f"{m.group(1)}{int(m.group(2))}{m.group(3)}" if m else None


def cuneiform_name(ch: str) -> Optional[str]:
    """Conventional sign name of one cuneiform character (``"𒀀"`` -> ``"A"``), or None."""
    m = _CUNEIFORM.match(unicodedata.name(ch, ""))
    return m.group(1) if m else None


def signs(text: str) -> List[Sign]:
    """Every hieroglyph or cuneiform sign in ``text``, in order; other characters are skipped."""
    out = []
    for ch in text:
        name = unicodedata.name(ch, "")
        cp = f"U+{ord(ch):04X}"
        if name.startswith("EGYPTIAN HIEROGLYPH FORMAT CONTROL") or name.startswith("EGYPTIAN HIEROGLYPH VERTICAL") \
                or name.startswith("EGYPTIAN HIEROGLYPH HORIZONTAL") or name.startswith("EGYPTIAN HIEROGLYPH INSERT"):
            out.append(Sign(ch, cp, "Egyp", name.replace("EGYPTIAN HIEROGLYPH ", ""), "control"))
        elif (g := gardiner(ch)) is not None:
            out.append(Sign(ch, cp, "Egyp", g))
        elif (c := cuneiform_name(ch)) is not None:
            kind = "number" if "NUMERIC" in name else "punctuation" if "PUNCTUATION" in name else "sign"
            out.append(Sign(ch, cp, "Xsux", c, kind))
    return out


def sign_list(text: str, sep: str = "-") -> str:
    """Signs joined in reading order: ``"A1-D58"`` / ``"A-ASH"``. Words (spaces) are kept."""
    words = []
    for word in text.split():
        codes = [s.code for s in signs(word) if s.kind in ("sign", "number")]
        if codes:
            words.append(sep.join(codes))
    return " ".join(words)
