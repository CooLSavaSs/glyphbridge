"""Translation router.

For every sentence:

1. **Detect** the source language (GlotLID) unless it is given.
2. **Route** to the first backend that supports the pair: Opus-MT direct model ->
   TranslateGemma (if enabled) -> MADLAD-400. If no backend supports the pair
   directly, pivot through English.
3. **Check** the meaning of each translation against its source (LaBSE). Sentences
   that fail go to the next backend; the best attempt wins. If none passes, the
   result is returned with ``flagged=True`` (shown as a warning by the CLI).
   Numbers and names are also checked without any model (``checker.consistency``).

``confidence`` is the checker's similarity when the checker is installed,
otherwise the model's own token probability (None when the backend gives none).
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass, field, replace
from typing import Dict, List, Optional, Sequence

import logging
import os
import unicodedata

from . import cards, lid
from . import backends as backends_mod
from .backends import CACHE, Backend, BackendUnavailable, default_backends
from .checker import Checker, consistency
from .emotion import Emotion
from .glossary import Glossary
from .memory import Memory
from . import routes as routes_table

log = logging.getLogger("glyphbridge")

PIVOT = "en"

# Core languages listed by ``glyphbridge languages``. Many more work through MADLAD-400.
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "en": "English", "tr": "Turkish", "de": "German", "fr": "French", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "ru": "Russian", "ar": "Arabic", "zh": "Chinese",
    "ja": "Japanese", "ko": "Korean", "hi": "Hindi", "nl": "Dutch", "pl": "Polish",
    "uk": "Ukrainian", "fa": "Persian", "el": "Greek", "he": "Hebrew", "sv": "Swedish",
    "id": "Indonesian", "vi": "Vietnamese", "th": "Thai", "bn": "Bengali", "ur": "Urdu",
    "sw": "Swahili", "az": "Azerbaijani", "kk": "Kazakh", "uz": "Uzbek", "ka": "Georgian",
    "la": "Latin", "ku": "Kurdish",
}


def usable_ram_mb() -> int:
    """RAM a card may use: the free-RAM budget plus what the cards already loaded hold,
    because the cache unloads them to make room. Without the second part a card that
    would fit after unloading counted as "too big" and was skipped (FLORES re-run:
    MADLAD lost Mongolian, Kazakh, Tibetan, Uyghur and Khmer to a weaker card)."""
    return CACHE.room_mb()


class TranslationError(RuntimeError):
    """Raised when a translation cannot be produced."""


@dataclass
class TranslationResult:
    translation: str
    source: str
    target: str
    confidence: Optional[float]
    model: str
    flagged: bool = False
    similarity: Optional[float] = None
    attempts: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    tone: Optional[str] = None   # source tone from the emotion module, when it is on
    # Separate signals, so nobody has to guess what `confidence` mixes together:
    detected_script: Optional[str] = None          # ISO 15924 of the source text: Latn, Arab, ...
    ocr_confidence: Optional[float] = None         # Tesseract's word confidence (0-1), images only
    translation_confidence: Optional[float] = None  # the model's own token probability (0-1)
    consistency_issues: List[str] = field(default_factory=list)  # numbers / names / empty output
    expert_review_required: bool = False           # see needs_review()
    box: Optional[tuple] = None                    # photos: (left, top, right, bottom) of the line in pixels

    def to_dict(self) -> dict:
        return asdict(self)


# A person should check the result when any of these hold. The thresholds are starting
# points, not measured cut-offs (OCR and probability calibration are not measured yet).
OCR_REVIEW_BELOW = 0.70
PROBABILITY_REVIEW_BELOW = 0.50


def needs_review(r: TranslationResult) -> bool:
    """True when the result failed a check, the OCR was unsure, or no meaning check ran
    and the model itself was unsure."""
    if r.flagged or r.issues:
        return True
    if r.ocr_confidence is not None and r.ocr_confidence < OCR_REVIEW_BELOW:
        return True
    return (r.similarity is None and r.translation_confidence is not None
            and r.translation_confidence < PROBABILITY_REVIEW_BELOW)


_SCRIPT_CODES = {
    "LATIN": "Latn", "ARABIC": "Arab", "CYRILLIC": "Cyrl", "GREEK": "Grek", "HEBREW": "Hebr",
    "CJK": "Hani", "HIRAGANA": "Jpan", "KATAKANA": "Jpan", "HANGUL": "Hang",
    "DEVANAGARI": "Deva", "BENGALI": "Beng", "TAMIL": "Taml", "TELUGU": "Telu", "THAI": "Thai",
    "GEORGIAN": "Geor", "ARMENIAN": "Armn", "ETHIOPIC": "Ethi", "SYRIAC": "Syrc", "TIBETAN": "Tibt",
    "KHMER": "Khmr", "MYANMAR": "Mymr", "GUJARATI": "Gujr", "GURMUKHI": "Guru", "KANNADA": "Knda",
    "MALAYALAM": "Mlym", "SINHALA": "Sinh", "LAO": "Laoo", "MONGOLIAN": "Mong", "THAANA": "Thaa",
    "EGYPTIAN": "Egyp", "CUNEIFORM": "Xsux", "RUNIC": "Runr", "COPTIC": "Copt", "OLD": "Ital",
}


def detect_script(text: str) -> Optional[str]:
    """Most common writing system among the letters of ``text`` (ISO 15924), or None."""
    counts: Dict[str, int] = {}
    for ch in text:
        if not ch.isalpha():
            continue
        word = unicodedata.name(ch, "").split(" ")[0]
        code = _SCRIPT_CODES.get(word, word.title()[:4] if word else None)
        if code:
            counts[code] = counts.get(code, 0) + 1
    return max(counts, key=counts.get) if counts else None


class Engine:
    def __init__(self, backends: Optional[List[Backend]] = None, checker: Optional[Checker] = None,
                 memory: Optional[Memory] = None, emotion: Optional[Emotion] = None,
                 glossary: Optional[Glossary] = None):
        from . import profiles
        profiles.apply_from_env()  # GLYPHBRIDGE_PROFILE for the API, MCP and Python too
        if cards.offline():
            os.environ["HF_HUB_OFFLINE"] = "1"  # use installed cards only, never download
        self.backends = backends if backends is not None else default_backends()
        self.checker = checker if checker is not None else Checker()
        # Your own fixed translations (idioms, terms), used before any model.
        self.memory = memory if memory is not None else Memory.from_env()
        # Emotion module card: flags translations whose tone flips.
        self.emotion = emotion if emotion is not None else Emotion()
        # Your fixed terms: kept consistent across every sentence of a document.
        self.glossary = glossary if glossary is not None else Glossary.from_env()
        # Results cache: a sentence repeated in a document is translated only once.
        self._cache: "OrderedDict[tuple, TranslationResult]" = OrderedDict()
        self.cache_size = int(os.environ.get("GLYPHBRIDGE_RESULT_CACHE", "2048"))

    def fingerprint(self) -> tuple:
        """Everything that can change a translation besides the text and languages:
        which cards are in use (and their pinned revisions), the routing preference
        and the checker threshold. Part of the cache key, so a result from one model,
        model version or setting is never reused for another."""
        cards_used = tuple((b.name, getattr(b, "revision", None) or getattr(b, "repo", None)
                            or getattr(b, "model_id", None)) for b in self.backends)
        return (cards_used, os.environ.get("GLYPHBRIDGE_PREFER", "speed"),
                getattr(self.checker, "threshold", None),
                # The RAM budget matters only through the card order it produces. The raw
                # number follows free RAM and changes all the time on a real PC, which made
                # every lookup a cache miss.
                tuple(b.name for b in self._ordered()),
                routes_table.VERSION if routes_table.enabled() else None,
                os.environ.get("GLYPHBRIDGE_MEANING", "0"),
                self.memory.fingerprint(), self.emotion.enabled(), self.glossary.fingerprint(),
                os.environ.get("GLYPHBRIDGE_CONTEXT", "0"))

    def _ordered(self) -> List[Backend]:
        """Backends in the order to try them.

        * ``GLYPHBRIDGE_PREFER=quality`` tries TranslateGemma before the fast Opus-MT models.
        * Cards whose estimated RAM does not fit the current RAM budget move to the end,
          so a small card is tried before a large one would push the PC into swap.
        """
        order = list(self.backends)
        if os.environ.get("GLYPHBRIDGE_PREFER", "speed") == "quality":
            order.sort(key=lambda b: 0 if b.name.startswith("gemma") else 1)
        budget = usable_ram_mb()
        return sorted(order, key=lambda b: 1 if getattr(b, "ram_mb", 0) > budget else 0)

    def candidates(self, source: str, target: str) -> List[list]:
        """Routes to try, best first. A route is a list of (backend, src, tgt) hops."""
        backends = self._ordered()

        def ok(b, src, tgt):
            # One broken card must not take the whole translation down.
            try:
                return b.supports(src, tgt)
            except Exception as exc:  # noqa: BLE001
                log.warning("backend %s failed on %s-%s: %s", b.name, src, tgt, exc)
                return False

        direct = [b for b in backends if ok(b, source, target)]
        # Measured route table: for pairs with golden-set numbers the best card goes first.
        # An explicit GLYPHBRIDGE_PREFER=quality wins over it, and a card that does not fit
        # the RAM budget stays behind the ones that do.
        if os.environ.get("GLYPHBRIDGE_PREFER", "speed") != "quality":
            budget = usable_ram_mb()
            keys = routes_table.rank([b.name for b in direct], source, target)
            direct = [b for _, _, b in sorted(
                ((1 if getattr(b, "ram_mb", 0) > budget else 0, k, b) for k, b in zip(keys, direct)),
                key=lambda t: (t[0], t[1]))]
        routes = [[(b, source, target)] for b in direct]
        if PIVOT not in (source, target):
            first = next((b for b in backends if ok(b, source, PIVOT)), None)
            second = next((b for b in backends if ok(b, PIVOT, target)), None)
            if first and second:
                routes.append([(first, source, PIVOT), (second, PIVOT, target)])
        return routes

    def _run_route(self, route, texts: Sequence[str]):
        current, probs = list(texts), [1.0] * len(texts)
        for backend, src, tgt in route:
            out = backend.translate(current, src, tgt)
            current = [t for t, _ in out]
            probs = [None if p is None or q is None else p * q for p, (_, q) in zip(probs, out)]
        label = " -> ".join(f"{b.name}:{s}-{t}" for b, s, t in route)
        return current, probs, label

    def translate_batch(self, texts: Sequence[str], target: str, source: str = "auto") -> List[TranslationResult]:
        """Translate texts, reusing cached results and translating each distinct text once."""
        if not texts:
            return []
        if source in (None, "", "auto"):
            sources = detect_each(texts)
            if len(set(sources)) > 1:
                # Mixed-language input: translate each language group on its own.
                out: List[Optional[TranslationResult]] = [None] * len(texts)
                for lang in dict.fromkeys(sources):
                    idx = [i for i, s in enumerate(sources) if s == lang]
                    for i, r in zip(idx, self.translate_batch([texts[i] for i in idx], target, lang)):
                        out[i] = r
                return out  # type: ignore[return-value]
            source = sources[0]
        source, target = source.lower(), target.lower()
        fp = self.fingerprint()
        ctx: Dict[str, str] = {}
        if backends_mod.context_mode():
            # Context window: each text sees the one before it; it is part of the cache key,
            # because the same sentence can translate differently after different paragraphs.
            for i, t in enumerate(texts):
                if i and t not in ctx:
                    ctx[t] = texts[i - 1]
        keys = [(_normalize(t), source, target, fp, _normalize(ctx.get(t, ""))) for t in texts]
        todo = list(dict.fromkeys(k for k in keys if k not in self._cache))
        if todo:
            first_text = {}
            for t, k in zip(texts, keys):
                first_text.setdefault(k, t)
            backends_mod.set_context(ctx)
            try:
                fresh = self._translate_uncached([first_text[k] for k in todo], target, source)
            finally:
                backends_mod.set_context({})
            for k, r in zip(todo, fresh):
                self._cache[k] = r
                self._cache.move_to_end(k)
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        results = []
        for t, k in zip(texts, keys):
            r = self._cache[k]
            r = replace(r, attempts=list(r.attempts), issues=list(r.issues),
                        consistency_issues=list(r.consistency_issues), detected_script=detect_script(t))
            r.expert_review_required = needs_review(r)
            results.append(r)
        return results

    def _translate_uncached(self, texts: Sequence[str], target: str, source: str) -> List[TranslationResult]:
        if not texts:
            return []
        target = target.lower()
        if source in (None, "", "auto"):
            detected = lid.detect(" ".join(texts))
            if not detected:
                raise TranslationError("Could not detect the source language; pass source=...")
            source = detected
        source = source.lower()
        if source == target:
            return [TranslationResult(t, source, target, 1.0, "identity") for t in texts]

        hits = {i: m for i, t in enumerate(texts) if (m := self.memory.get(t, source, target)) is not None}
        if hits:
            rest = [i for i in range(len(texts)) if i not in hits]
            done = dict(zip(rest, self._translate_uncached([texts[i] for i in rest], target, source)))
            for i, m in hits.items():
                done[i] = TranslationResult(m, source, target, 1.0, "memory", attempts=["memory"])
            return [done[i] for i in range(len(texts))]

        routes = self.candidates(source, target)
        if not routes:
            raise TranslationError(f"Language pair not supported yet: {source} -> {target}")

        best: List[Optional[TranslationResult]] = [None] * len(texts)
        pending = list(range(len(texts)))
        tones = self.emotion.labels(texts)
        def run(routes, pending):
            for route in routes:
                if not pending:
                    break
                try:
                    outs, probs, label = self._run_route(route, [texts[i] for i in pending])
                except BackendUnavailable:
                    continue
                sims = self.checker.similarity([texts[i] for i in pending], outs)
                out_tones = self.emotion.labels(outs) if any(tones) else [None] * len(outs)
                still = []
                for i, out, prob, sim, out_tone in zip(pending, outs, probs, sims, out_tones):
                    conf = sim if sim is not None else prob
                    found = consistency(texts[i], out, source) + self.glossary.check(texts[i], out, source, target)
                    issues = list(found)
                    flip = self.emotion.flipped(tones[i], out_tone)
                    if flip:
                        issues.append(flip)
                    ok = self.checker.passes(sim) and not issues
                    prev = best[i]
                    attempts = (prev.attempts if prev else []) + [label]
                    cand = TranslationResult(out, source, target, None if conf is None else round(conf, 4), label,
                                             flagged=not ok, similarity=sim, attempts=attempts, issues=issues,
                                             tone=tones[i][0] if tones[i] else None,
                                             translation_confidence=None if prob is None else round(prob, 4),
                                             consistency_issues=found)
                    better = (len(cand.issues), -(cand.confidence or 0)) < (len(prev.issues), -(prev.confidence or 0)) if prev else True
                    if prev is None or ok or better:
                        best[i] = cand
                    else:
                        prev.attempts = attempts
                    if not ok:
                        still.append(i)
                pending = still

        refused = CACHE.refusals
        run(routes, pending)
        if any(r is None for r in best) and CACHE.refusals > refused:
            # Every card that could do it was too big for the RAM free right now. Translating
            # slowly (swap) beats not translating: retry once, smallest route first.
            backends_mod.logger.warning("no card fits the free RAM; loading the smallest anyway (%s)",
                                        CACHE.last_refusal)
            with CACHE.oversize():
                run(sorted(routes, key=lambda r: sum(getattr(b, "ram_mb", 0) for b, _, _ in r)),
                    [i for i, r in enumerate(best) if r is None])

        if any(r is None for r in best):
            raise TranslationError(missing_card_hint(source, target))
        return best  # type: ignore[return-value]

    def translate(self, text: str, target: str, source: str = "auto") -> TranslationResult:
        return self.translate_batch([text], target=target, source=source)[0]


# Below this many letters a segment is too short to identify reliably ("OK", "2024", a name),
# so it takes the language of the whole input instead.
MIN_DETECT_LETTERS = 20


def missing_card_hint(source: str, target: str) -> str:
    """What to install to translate source -> target, with download size and RAM."""
    from .backends import HYMT2_LANGS
    card = "hymt2-q4" if source in HYMT2_LANGS and target in HYMT2_LANGS else "madlad-int8"
    c = cards.CARDS[card]
    lines = [f"No installed card can translate {source} -> {target}.",
             f"Install one: glyphbridge cards install {card}   "
             f"(download {c.disk}, about {c.ram_mb / 1000:.1f} GB RAM while translating)"]
    if card == "hymt2-q4":
        m = cards.CARDS["madlad-int8"]
        lines.append(f"For 400+ languages add: glyphbridge cards install madlad-int8   "
                     f"(download {m.disk}, about {m.ram_mb / 1000:.1f} GB RAM)")
    lines.append('The cards need the engines: pip install "glyphbridge[8gb]" (no PyTorch). '
                 "See all cards: glyphbridge cards")
    return "\n".join(lines)


def detect_each(texts: Sequence[str]) -> List[str]:
    """Source language per segment: each long-enough segment is detected on its own (so a
    Turkish paragraph inside an English document is not translated as English); short or
    undetectable segments fall back to the language of the whole input."""
    whole: Optional[str] = None
    tried_whole = False
    out: List[str] = []
    for t in texts:
        code = lid.detect(t) if sum(ch.isalpha() for ch in t) >= MIN_DETECT_LETTERS else None
        if not code:
            if not tried_whole:
                whole, tried_whole = lid.detect(" ".join(texts)), True
            code = whole
        if not code:
            raise TranslationError("Could not detect the source language; pass source=...")
        out.append(code.lower())
    return out


def _normalize(text: str) -> str:
    """Cache-key form of a text: Unicode NFC, whitespace collapsed."""
    return " ".join(unicodedata.normalize("NFC", text).split())


_default: Optional[Engine] = None


ASK_TARGET_EN = "Which language should I translate this into?"


def ask_target(text: str, engine: Optional["Engine"] = None) -> dict:
    """Glyphbridge only translates. Given text but no target language, it does not answer
    the text (a greeting, a question, a story): it asks which language to translate into,
    in the language the text is written in when it can."""
    src = None
    try:
        src = lid.detect(text)
    except Exception:  # noqa: BLE001 - detection is optional here
        src = None
    question = ASK_TARGET_EN
    if src and src != "en":
        try:
            question = (engine or get_engine()).translate(ASK_TARGET_EN, target=src, source="en").translation
        except Exception:  # noqa: BLE001 - fall back to English
            question = ASK_TARGET_EN
    return {"needs_target": True, "question": question, "question_en": ASK_TARGET_EN,
            "detected_source": src, "text": text}


def parse_language(answer: str) -> Optional[str]:
    """'de', 'German' -> 'de'. None if the answer is not a known language."""
    a = " ".join(answer.strip().strip(".!?。").lower().split())
    if a in _CODE_WORDS:
        return None  # "hi", "no"... are replies, not languages; type "Hindi" / "Norwegian"
    if a in SUPPORTED_LANGUAGES:
        return a
    for code, name in SUPPORTED_LANGUAGES.items():
        if a == name.lower():
            return code
    if a in LANGUAGE_WORDS:
        return LANGUAGE_WORDS[a]
    if 2 <= len(a) <= 3 and a.isascii() and a.isalpha() and a not in _CODE_WORDS and a in _known_codes():
        return a
    return None


# Language names people type when asked, beyond the English names above (Turkish first).
LANGUAGE_WORDS = {
    "ingilizce": "en", "türkçe": "tr", "almanca": "de", "fransızca": "fr", "ispanyolca": "es",
    "italyanca": "it", "portekizce": "pt", "rusça": "ru", "arapça": "ar", "çince": "zh",
    "japonca": "ja", "korece": "ko", "hintçe": "hi", "hollandaca": "nl", "lehçe": "pl",
    "latince": "la", "farsça": "fa", "persian": "fa", "latin": "la", "yunanca": "el", "greek": "el",
    "svahili": "sw", "swahili": "sw", "kiswahili": "sw", "urduca": "ur", "urdu": "ur",
    "ibranice": "he", "hebrew": "he", "vietnamca": "vi", "vietnamese": "vi", "endonezce": "id",
    "indonesian": "id", "bengalce": "bn", "bengali": "bn", "tayca": "th", "thai": "th",
    "ukraynaca": "uk", "ukrainian": "uk", "kazakça": "kk", "kazakh": "kk", "özbekçe": "uz", "uzbek": "uz",
    "azerice": "az", "azerbaijani": "az", "azerbaycan türkçesi": "az", "kürtçe": "ku", "kurdish": "ku",
    "uygurca": "ug", "uyghur": "ug", "moğolca": "mn", "mongolian": "mn", "tibetçe": "bo", "tibetan": "bo",
    "yoruba": "yo", "hausa": "ha", "amharca": "am", "amharic": "am", "somalice": "so", "somali": "so",
    "zuluca": "zu", "zulu": "zu", "keçuva": "qu", "quechua": "qu", "guarani": "gn", "baskça": "eu",
    "basque": "eu", "galce": "cy", "welsh": "cy", "maltaca": "mt", "maltese": "mt", "süryanice": "syr",
    "syriac": "syr", "osmanlıca": "ota", "ottoman turkish": "ota",
    # Endonyms: the language's own name for itself.
    "english": "en", "deutsch": "de", "français": "fr", "francais": "fr", "español": "es", "espanol": "es",
    "italiano": "it", "português": "pt", "portugues": "pt", "русский": "ru", "العربية": "ar",
    "中文": "zh", "汉语": "zh", "日本語": "ja", "한국어": "ko", "हिन्दी": "hi", "nederlands": "nl",
    "polski": "pl", "فارسی": "fa", "ελληνικά": "el", "עברית": "he", "tiếng việt": "vi",
    "bahasa indonesia": "id", "বাংলা": "bn", "ไทย": "th", "українська": "uk", "қазақша": "kk",
    "oʻzbekcha": "uz", "o'zbekcha": "uz", "azərbaycanca": "az", "kurdî": "ku", "ئۇيغۇرچە": "ug",
    "монгол": "mn", "བོད་སྐད": "bo", "èdè yorùbá": "yo", "yorùbá": "yo", "አማርኛ": "am", "soomaali": "so",
    "isizulu": "zu", "runasimi": "qu", "avañeʼẽ": "gn", "euskara": "eu", "cymraeg": "cy", "malti": "mt",
    "ܣܘܪܝܝܐ": "syr", "اردو": "ur",
}

# Two- and three-letter codes are accepted as an answer too, except those that are also
# everyday words ("hi", "no", "so"...), which would turn a reply into a language by accident.
_CODE_WORDS = set("hi no so to am be is it me my he we an as at by do go if in of on or up us ok".split())


def _known_codes() -> set:
    from .backends import GEMMA_DEFAULT_LANGS, HYMT2_LANGS
    return set(SUPPORTED_LANGUAGES) | set(GEMMA_DEFAULT_LANGS) | set(HYMT2_LANGS) | set(LANGUAGE_WORDS.values())


def get_engine() -> Engine:
    global _default
    if _default is None:
        _default = Engine()
    return _default


def translate(text: str, to: str, source: str = "auto") -> TranslationResult:
    """Translate ``text`` into the language ``to``.

    >>> import glyphbridge
    >>> glyphbridge.translate("Merhaba dünya", to="en", source="tr").translation
    'Hello world'
    """
    return get_engine().translate(text, target=to, source=source)
