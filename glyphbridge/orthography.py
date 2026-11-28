"""Write the output in the script a language is normally written in today.

Some models answer in an older or less common script: MADLAD-400 writes Uzbek in Cyrillic,
while Uzbekistan has used the Latin alphabet officially since 1995 and most Uzbek text online
and in schools is Latin. Measured on FLORES-200 (English -> Uzbek, 50 sentences): chrF 2.0
with the Cyrillic output, because the human reference is Latin.

The fix is a fixed, rule-based letter mapping (no model, no download), applied only when the
output is in the "wrong" script for the target language.
"""
from typing import Dict

# Uzbek Cyrillic -> Uzbek Latin (the 1995 alphabet, apostrophe written as ASCII "'", as most
# people type it and as FLORES-200 uses it). Е is handled separately (e / ye).
_UZ: Dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ё": "yo", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "sh", "ъ": "'", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}
_UZ_VOWELS = set("аеёиоуэюяўАЕЁИОУЭЮЯЎ")


def _cyrillic_letters(text: str) -> int:
    return sum(1 for ch in text if "Ѐ" <= ch <= "ӿ")


def _latin_letters(text: str) -> int:
    return sum(1 for ch in text if ch.isascii() and ch.isalpha())


def uzbek_cyrillic_to_latin(text: str) -> str:
    out = []
    for i, ch in enumerate(text):
        low = ch.lower()
        prev = text[i - 1] if i else ""
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if low == "е":
            # "ye" at the start of a word and after a vowel or a hard/soft sign, else "e".
            lat = "ye" if (not prev.isalpha() or prev in _UZ_VOWELS or prev.lower() in "ъь") else "e"
        elif low in _UZ:
            lat = _UZ[low]
        else:
            out.append(ch)
            continue
        if ch != low and lat:
            # Capital: "Ш" -> "Sh" in a normal word, "SH" when the whole word is capitals.
            lat = lat.upper() if (nxt.isalpha() and nxt.isupper()) or (prev.isalpha() and prev.isupper()) else lat[0].upper() + lat[1:]
        out.append(lat)
    return "".join(out)


# target language -> converter from the script models tend to use to the usual one.
_CONVERT = {"uz": uzbek_cyrillic_to_latin}


def to_usual_script(text: str, target: str) -> str:
    """``text`` in the script ``target`` is normally written in today; unchanged when it
    already is, or when no conversion is known for that language."""
    fix = _CONVERT.get(target.lower().split("-")[0].split("_")[0])
    if fix is None or target.lower() in ("uz-cyrl", "uz_cyrl"):
        return text
    if _cyrillic_letters(text) <= _latin_letters(text):
        return text
    return fix(text)
