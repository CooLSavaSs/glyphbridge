"""Translation backends.

Each backend wraps one family of open models. The router in ``engine.py`` asks
each backend whether it can handle a language pair and tries them in order:

1. ``opus``    Helsinki-NLP Opus-MT / tc-big (CC-BY 4.0). Small (~300 MB) and fast,
               used when a direct model exists for the pair (e.g. en→tr tc-big).
2. ``gemma``   Google TranslateGemma 4B (Gemma terms of use). Highest quality for its
               ~55 evaluated languages; can also read text in images. Opt-in, because
               the weights are gated: accept the terms on Hugging Face first.
3. ``madlad``  Google MADLAD-400 3B (Apache 2.0). 400+ languages; covers rare ones
               (Latin, Ancient Greek, Syriac, ...).

Each model is a *card* (see ``cards.py``). Cards are loaded only when a sentence
needs them and unloaded when the RAM budget is full, so an 8 GB machine only ever
runs what the current sentence needs.
"""

from __future__ import annotations

import logging
import math
import os
import threading
from collections import OrderedDict
from typing import Iterable, List, Optional, Sequence, Tuple

from .cards import CARDS, OPUS_RAM_MB, _cached_repos, is_installed, offline, pinned

logger = logging.getLogger("glyphbridge")

Output = List[Tuple[str, Optional[float]]]  # (translation, model probability 0–1, or None if unknown)


class BackendUnavailable(RuntimeError):
    """The backend cannot load its model (not installed, gated, offline, ...)."""


def free_ram_mb() -> Optional[int]:
    """RAM the system can give right now without swapping (MB), or None if unknown."""
    try:
        import psutil  # type: ignore
        return int(psutil.virtual_memory().available / 1024 / 1024)
    except Exception:  # noqa: BLE001 - no psutil / unsupported platform
        return None


def _process_rss_mb() -> Optional[int]:
    try:
        import psutil  # type: ignore
        return int(psutil.Process().memory_info().rss / 1024 / 1024)
    except Exception:  # noqa: BLE001
        return None


def measured_ram_path() -> str:
    return os.environ.get("GLYPHBRIDGE_MEASURED_RAM") or os.path.join(
        os.path.expanduser("~"), ".cache", "glyphbridge", "measured_ram.json")


class ModelCache:
    """Process-wide cache of loaded cards, sized to the RAM that is free right now.

    Only the cards a sentence needs are loaded; the least recently used card is
    unloaded first to make room.

    Fixed budget (``budget_mb=`` or GLYPHBRIDGE_RAM_BUDGET_MB): the estimated RAM of the
    loaded cards stays under it; a single card larger than the budget is still allowed
    on its own (the old behaviour, kept for tests and for people who set a number).

    Free-memory mode (the default): before each load the cache reads how much RAM the
    system can free right now and keeps GLYPHBRIDGE_RAM_MARGIN_MB (default 1024) spare.
    A card that does not fit even after unloading the others is skipped *for now*
    (not marked broken), so the route moves on to the next, smaller card instead of
    pushing the machine into swap. GLYPHBRIDGE_ALLOW_OVERSIZE=1 loads it anyway.

    Measured RAM: the first time a card loads, the growth of this process is recorded
    in ~/.cache/glyphbridge/measured_ram.json. Later decisions use the larger of that
    measurement and the card's estimate, so a card whose estimate was too optimistic is
    not loaded into a machine that cannot hold it. (Weights that llama.cpp memory-maps
    are read lazily, so a load-time measurement can be lower than the real need; that
    is why it only ever raises the estimate.)
    """

    def __init__(self, budget_mb: Optional[int] = None, max_models: Optional[int] = None):
        self._fixed_budget = budget_mb
        self.max_models = max_models or int(os.environ.get("GLYPHBRIDGE_MAX_MODELS", "3"))
        self.margin_mb = int(os.environ.get("GLYPHBRIDGE_RAM_MARGIN_MB", "1024"))
        self._items: "OrderedDict[str, Tuple[object, int]]" = OrderedDict()
        self._failed: set = set()
        self._lock = threading.Lock()
        self._measured: Optional[dict] = None
        self.last_refusal: Optional[str] = None
        self.refusals = 0                  # how many loads were skipped for lack of RAM
        self._force = False

    @property
    def budget_mb(self) -> Optional[int]:
        """The fixed budget, or None in free-memory mode (read at call time, so setting
        GLYPHBRIDGE_RAM_BUDGET_MB after import still works)."""
        if self._fixed_budget is not None:
            return self._fixed_budget
        env = os.environ.get("GLYPHBRIDGE_RAM_BUDGET_MB")
        return int(env) if env else None

    def room_mb(self) -> int:
        """RAM a card may take: what is free now (or the fixed budget) plus what the loaded
        cards hold, because they are unloaded to make room."""
        if self.budget_mb is not None:
            return self.budget_mb + self.used_mb
        free = free_ram_mb()
        if free is None:
            return 4096 + self.used_mb
        return max(free - self.margin_mb, 0) + self.used_mb

    # -- measured RAM ---------------------------------------------------------------
    def measured(self) -> dict:
        if self._measured is None:
            try:
                import json
                with open(measured_ram_path(), encoding="utf-8") as f:
                    data = json.load(f)
                self._measured = {k: int(v) for k, v in data.items()} if isinstance(data, dict) else {}
            except Exception:  # noqa: BLE001 - missing or unreadable file = nothing measured yet
                self._measured = {}
        return self._measured

    def _record(self, key: str, mb: int) -> None:
        data = self.measured()
        if mb <= data.get(key, 0):
            return
        data[key] = mb
        try:
            import json
            path = measured_ram_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1, sort_keys=True)
            os.replace(tmp, path)
        except OSError:
            pass                           # a read-only home must not stop translation

    def need_mb(self, key: str, estimate_mb: int) -> int:
        return max(estimate_mb, self.measured().get(key, 0))

    # -- cache ----------------------------------------------------------------------
    @property
    def used_mb(self) -> int:
        return sum(ram for _, ram in self._items.values())

    def _unload_oldest(self) -> None:
        self._items.popitem(last=False)
        import gc
        gc.collect()

    def _make_room(self, key: str, need: int) -> bool:
        """Unload old cards until `need` MB fits; False if it cannot fit right now."""
        while self._items and len(self._items) >= self.max_models:
            self._unload_oldest()
        if self.budget_mb is not None:
            while self._items and self.used_mb + need > self.budget_mb:
                self._unload_oldest()
            return True                    # fixed budget: a lone oversize card is allowed
        free = free_ram_mb()
        if free is None:
            return True                    # cannot measure: behave as before
        while self._items and free - self.margin_mb < need:
            self._unload_oldest()
            free = free_ram_mb() or free
        if free - self.margin_mb >= need or self._force or os.environ.get("GLYPHBRIDGE_ALLOW_OVERSIZE") == "1":
            return True
        self.refusals += 1
        self.last_refusal = (f"{key}: needs ~{need} MB, only {max(free - self.margin_mb, 0)} MB "
                             f"can be freed now ({free} MB free, {self.margin_mb} MB kept spare)")
        logger.warning("skipping card for now: %s", self.last_refusal)
        return False

    def get(self, key: str, loader, ram_mb: int = 0):
        need = self.need_mb(key, ram_mb)
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key][0]
            if key in self._failed:
                return None
            if not self._make_room(key, need):
                return None                # not broken, just too big right now
        before = _process_rss_mb()
        try:
            value = loader()
        except BackendUnavailable:
            with self._lock:
                self._failed.add(key)
            return None
        after = _process_rss_mb()
        if before is not None and after is not None and after - before > 50:
            self._record(key, after - before)
        with self._lock:
            self._items[key] = (value, need)
        return value

    def oversize(self):
        """Context manager: allow loads that do not fit (the engine's last resort)."""
        import contextlib

        @contextlib.contextmanager
        def ctx():
            self._force = True
            try:
                yield
            finally:
                self._force = False
        return ctx()

    def status(self) -> dict:
        """What is loaded, what was measured and how much RAM is free (for `glyphbridge ram`)."""
        return {"mode": "fixed budget" if self.budget_mb is not None else "free memory",
                "budget_mb": self.budget_mb, "free_mb": free_ram_mb(), "margin_mb": self.margin_mb,
                "loaded": {k: ram for k, (_, ram) in self._items.items()},
                "measured": dict(self.measured()), "last_refusal": self.last_refusal}

    def loaded(self, key: str) -> bool:
        return key in self._items

    def failed(self, key: str) -> bool:
        return key in self._failed


def has_transformers() -> bool:
    """PyTorch + Transformers are an extra (pip install "glyphbridge[transformers]"),
    not part of the light base install."""
    import importlib.util
    return all(importlib.util.find_spec(m) is not None for m in ("transformers", "torch"))


# Hugging Face existence checks, once per process: "does this model repo exist?" is a
# small metadata request, unlike loading the model (hundreds of MB of RAM).
_REPO_EXISTS: dict = {}


def repo_exists(name: str) -> bool:
    if name not in _REPO_EXISTS:
        try:
            from huggingface_hub import HfApi  # type: ignore
            _REPO_EXISTS[name] = bool(HfApi().repo_exists(name))
        except Exception:  # noqa: BLE001 - no network / no huggingface_hub: cannot download it either
            _REPO_EXISTS[name] = False
    return _REPO_EXISTS[name]


CACHE = ModelCache()


def _probability(score) -> float:
    try:
        return round(max(0.0, min(1.0, math.exp(float(score)))), 4)
    except (TypeError, ValueError, OverflowError):
        return 0.0


class Backend:
    name = "base"

    def supports(self, source: str, target: str) -> bool:
        raise NotImplementedError

    def translate(self, texts: Sequence[str], source: str, target: str) -> Output:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Low-RAM mode (GLYPHBRIDGE_LOW_RAM=1): large Transformers cards keep the layers that do
# not fit GLYPHBRIDGE_LOW_RAM_MB (default 3000) on disk and stream them in while
# translating. GGUF cards (llama.cpp) already memory-map their weights from disk.
def low_ram() -> bool:
    return os.environ.get("GLYPHBRIDGE_LOW_RAM", "0") == "1"


def low_ram_budget_mb() -> int:
    return int(os.environ.get("GLYPHBRIDGE_LOW_RAM_MB", "3000"))


def offload_dir() -> str:
    path = os.environ.get("GLYPHBRIDGE_OFFLOAD_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "glyphbridge", "offload")
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
class OpusBackend(Backend):
    """Direct Opus-MT models; tries the larger tc-big model first."""

    name = "opus"
    ram_mb = OPUS_RAM_MB
    templates = ("Helsinki-NLP/opus-mt-tc-big-{src}-{tgt}", "Helsinki-NLP/opus-mt-{src}-{tgt}")

    def __init__(self, cache: ModelCache = CACHE, device: str = "cpu"):
        self.cache, self.device = cache, device

    def _load_named(self, name: str):
        def loader():
            try:
                from transformers import MarianMTModel, MarianTokenizer  # type: ignore
                tok = MarianTokenizer.from_pretrained(name)
                model = MarianMTModel.from_pretrained(name).to(self.device).eval()
                return tok, model
            except Exception as exc:  # noqa: BLE001 - any load failure means "not available"
                raise BackendUnavailable(str(exc)) from exc
        return self.cache.get(name, loader, OPUS_RAM_MB)

    # Models measured as broken: they load but return unusable text, so the next
    # template (the regular Opus-MT model) is used instead.
    # tc-big-ar-en: word salad for every golden-v2 sentence (chrF 1.3, CI #96), while
    # opus-mt-ar-en translates the same sentences correctly.
    # tc-big-el-en and tc-big-ko-en: same failure on golden-v3 (chrF 1.3 / 1.0, CI #102).
    broken = {"Helsinki-NLP/opus-mt-tc-big-ar-en", "Helsinki-NLP/opus-mt-tc-big-el-en",
              "Helsinki-NLP/opus-mt-tc-big-ko-en"}

    def _names(self, source: str, target: str):
        return [n for n in (tpl.format(src=source, tgt=target) for tpl in self.templates)
                if n not in self.broken]

    def _available(self, source: str, target: str) -> List[str]:
        """Model names that can be used for the pair, found WITHOUT loading any model:
        already loaded, installed in the Hugging Face cache, or (online) present on the Hub."""
        names = [n for n in self._names(source, target) if not self.cache.failed(n)]
        if not names or not has_transformers():
            return []
        cached = None
        out = []
        for name in names:
            if self.cache.loaded(name):
                out.append(name)
                continue
            if cached is None:
                cached = _cached_repos()
            if name in cached or (not offline() and repo_exists(name)):
                out.append(name)  # offline: only installed pair cards
        return out

    def _model_for(self, source: str, target: str):
        for name in self._available(source, target):
            loaded = self._load_named(name)
            if loaded is not None:
                return name, loaded
        return None, None

    def supports(self, source: str, target: str) -> bool:
        """Answers from names alone; the model is loaded only when a sentence is translated."""
        return bool(self._available(source, target))

    def translate(self, texts, source, target) -> Output:
        name, loaded = self._model_for(source, target)
        if loaded is None:
            raise BackendUnavailable(f"no Opus-MT model for {source}-{target}")
        tok, model = loaded
        import torch  # type: ignore
        batch = tok(list(texts), return_tensors="pt", padding=True, truncation=True).to(self.device)
        with torch.no_grad():
            out = model.generate(**batch, num_beams=4, max_new_tokens=512,
                                 output_scores=True, return_dict_in_generate=True)
        decoded = tok.batch_decode(out.sequences, skip_special_tokens=True)
        scores = getattr(out, "sequences_scores", None)
        return [(t, _probability(scores[i]) if scores is not None else 0.0) for i, t in enumerate(decoded)]


# ---------------------------------------------------------------------------
class MadladBackend(Backend):
    """MADLAD-400 3B: the wide-coverage fallback (400+ languages)."""

    name = "madlad"
    ram_mb = CARDS["madlad"].ram_mb
    model_id, revision = pinned("madlad", "GLYPHBRIDGE_MADLAD_MODEL")

    def __init__(self, cache: ModelCache = CACHE, device: str = "cpu"):
        self.cache, self.device = cache, device

    def _load(self):
        def loader():
            try:
                from transformers import AutoTokenizer, T5ForConditionalGeneration  # type: ignore
                import torch  # type: ignore
                tok = AutoTokenizer.from_pretrained(self.model_id, revision=self.revision)
                model = T5ForConditionalGeneration.from_pretrained(
                    self.model_id, revision=self.revision, torch_dtype=torch.bfloat16,
                    low_cpu_mem_usage=True).to(self.device).eval()
                return tok, model
            except (ImportError, OSError, ValueError) as exc:
                raise BackendUnavailable(str(exc)) from exc
        return self.cache.get(self.model_id, loader, CARDS["madlad"].ram_mb)

    def supports(self, source: str, target: str) -> bool:
        # MADLAD takes the target as a "<2xx>" tag and reads any source language.
        if os.environ.get("GLYPHBRIDGE_DISABLE_MADLAD") == "1":
            return False
        # The full-size card is opt-in; madlad-int8 is the default rare-language card.
        return is_installed(self.model_id) or os.environ.get("GLYPHBRIDGE_ENABLE_MADLAD_FULL") == "1"

    def translate(self, texts, source, target) -> Output:
        loaded = self._load()
        if loaded is None:
            raise BackendUnavailable("MADLAD-400 could not be loaded")
        tok, model = loaded
        import torch  # type: ignore
        prompts = [f"<2{target}> {t}" for t in texts]
        batch = tok(prompts, return_tensors="pt", padding=True, truncation=True).to(self.device)
        with torch.no_grad():
            out = model.generate(**batch, num_beams=4, max_new_tokens=512,
                                 output_scores=True, return_dict_in_generate=True)
        decoded = tok.batch_decode(out.sequences, skip_special_tokens=True)
        scores = getattr(out, "sequences_scores", None)
        return [(t, _probability(scores[i]) if scores is not None else 0.0) for i, t in enumerate(decoded)]


# ---------------------------------------------------------------------------
# Languages TranslateGemma was evaluated on that Glyphbridge routes to it by default.
# Override with GLYPHBRIDGE_GEMMA_LANGS="en,tr,de,...".
# Latin (la) is included because golden-v1 measured gemma-q4 at chrF 84.9 for la-en
# against 38.7 for madlad-int8.
GEMMA_DEFAULT_LANGS = (
    "ar bg bn ca cs da de el en es et fa fi fr gu he hi hr hu id it ja kn ko la lt lv ml mr "
    "nl no pa pl pt ro ru sk sl sr sv sw ta te th tr uk ur vi zh zu"
).split()


class GemmaBackend(Backend):
    """TranslateGemma (opt-in: accept the Gemma terms on Hugging Face, log in, then
    ``glyphbridge cards install gemma``)."""

    name = "gemma"
    ram_mb = CARDS["gemma"].ram_mb
    model_id, revision = pinned("gemma", "GLYPHBRIDGE_GEMMA_MODEL")

    def __init__(self, cache: ModelCache = CACHE, device: str = "cpu"):
        self.cache, self.device = cache, device
        env = os.environ.get("GLYPHBRIDGE_GEMMA_LANGS")
        self.langs = set(env.split(",")) if env else set(GEMMA_DEFAULT_LANGS)

    def enabled(self) -> bool:
        # Installing the "gemma" card turns it on; the env var forces it on.
        return os.environ.get("GLYPHBRIDGE_ENABLE_GEMMA") == "1" or is_installed(self.model_id)

    def _load(self):
        def loader():
            try:
                from transformers import AutoModelForImageTextToText, AutoProcessor  # type: ignore
                import torch  # type: ignore
                proc = AutoProcessor.from_pretrained(self.model_id, revision=self.revision)
                if low_ram():
                    # Layers that do not fit the RAM budget stay on disk and are streamed in
                    # one at a time while translating: slower, but a model larger than free
                    # RAM runs on an 8 GB PC.
                    model = AutoModelForImageTextToText.from_pretrained(
                        self.model_id, revision=self.revision, torch_dtype=torch.bfloat16,
                        low_cpu_mem_usage=True, device_map="auto",
                        max_memory={"cpu": f"{low_ram_budget_mb()}MiB"},
                        offload_folder=offload_dir(), offload_state_dict=True).eval()
                else:
                    model = AutoModelForImageTextToText.from_pretrained(
                        self.model_id, revision=self.revision, torch_dtype=torch.bfloat16,
                        low_cpu_mem_usage=True).to(self.device).eval()
                return proc, model
            except (ImportError, OSError, ValueError) as exc:
                raise BackendUnavailable(str(exc)) from exc
        ram = low_ram_budget_mb() if low_ram() else CARDS["gemma"].ram_mb
        return self.cache.get(self.model_id, loader, ram)

    def supports(self, source: str, target: str) -> bool:
        return self.enabled() and source in self.langs and target in self.langs

    def translate(self, texts, source, target) -> Output:
        loaded = self._load()
        if loaded is None:
            raise BackendUnavailable("TranslateGemma could not be loaded")
        proc, model = loaded
        import torch  # type: ignore
        results: Output = []
        for text in texts:
            messages = [{"role": "user", "content": [{
                "type": "text", "source_lang_code": source, "target_lang_code": target, "text": text,
            }]}]
            inputs = proc.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                              return_dict=True, return_tensors="pt").to(self.device)
            start = inputs["input_ids"].shape[-1]
            with torch.no_grad():
                out = model.generate(**inputs, max_new_tokens=512, do_sample=False,
                                     output_scores=True, return_dict_in_generate=True)
            seq = out.sequences[0][start:]
            decoded = proc.decode(seq, skip_special_tokens=True).strip()
            # Mean token log-probability of the greedy output.
            logps = []
            for step, tok_id in zip(out.scores, seq):
                logps.append(torch.log_softmax(step[0], dim=-1)[tok_id].item())
            conf = _probability(sum(logps) / len(logps)) if logps else 0.0
            results.append((decoded, conf))
        return results


# ---------------------------------------------------------------------------
# Small cards for 8 GB PCs: same models, community-quantized.

def _snapshot(repo: str, allow=None, revision: Optional[str] = None) -> str:
    try:
        from huggingface_hub import snapshot_download  # type: ignore
        return snapshot_download(repo, allow_patterns=allow, revision=revision)
    except Exception as exc:  # not installed, offline, gated...
        raise BackendUnavailable(str(exc)) from exc


class MadladInt8Backend(Backend):
    """MADLAD-400 3B converted to CTranslate2 int8 (~3 GB RAM instead of ~6.5 GB)."""

    name = "madlad-int8"
    ram_mb = CARDS["madlad-int8"].ram_mb
    repo, revision = pinned("madlad-int8", "GLYPHBRIDGE_MADLAD_INT8_MODEL")

    def __init__(self, cache: ModelCache = CACHE, device: str = "cpu"):
        self.cache, self.device = cache, device

    def _load(self):
        def loader():
            try:
                import ctranslate2  # type: ignore
                import sentencepiece as spm  # type: ignore
            except ImportError as exc:
                raise BackendUnavailable("needs: pip install 'glyphbridge[small]'") from exc
            path = _snapshot(self.repo, revision=self.revision)
            sp_file = next((os.path.join(path, f) for f in ("spiece.model", "sentencepiece.model")
                            if os.path.exists(os.path.join(path, f))), None)
            if sp_file is None:
                raise BackendUnavailable("tokenizer (spiece.model) missing from " + self.repo)
            threads = max(1, (os.cpu_count() or 2) - 1)
            translator = ctranslate2.Translator(path, device=self.device, compute_type="int8",
                                                intra_threads=threads)
            return translator, spm.SentencePieceProcessor(model_file=sp_file)
        return self.cache.get(self.repo, loader, CARDS["madlad-int8"].ram_mb)

    def supports(self, source: str, target: str) -> bool:
        if os.environ.get("GLYPHBRIDGE_DISABLE_MADLAD") == "1":
            return False
        return not offline() or is_installed(self.repo)

    def translate(self, texts, source, target) -> Output:
        loaded = self._load()
        if loaded is None:
            raise BackendUnavailable("MADLAD-400 int8 could not be loaded")
        translator, sp = loaded
        batch = [sp.encode(f"<2{target}> {t}", out_type=str) for t in texts]
        # Scores come back length-normalised (length_penalty=1): mean log-prob per token.
        res = translator.translate_batch(batch, beam_size=4, max_decoding_length=512,
                                         return_scores=True)
        return [(sp.decode(r.hypotheses[0]), _probability(r.scores[0])) for r in res]


# Language names for the TranslateGemma prompt.
LANG_NAMES = {
    "ar": "Arabic", "bg": "Bulgarian", "bn": "Bengali", "ca": "Catalan", "cs": "Czech", "da": "Danish",
    "de": "German", "el": "Greek", "en": "English", "es": "Spanish", "et": "Estonian", "fa": "Persian",
    "fi": "Finnish", "fr": "French", "gu": "Gujarati", "he": "Hebrew", "hi": "Hindi", "hr": "Croatian",
    "hu": "Hungarian", "id": "Indonesian", "it": "Italian", "ja": "Japanese", "kn": "Kannada",
    "ko": "Korean", "la": "Latin", "lt": "Lithuanian", "lv": "Latvian", "ml": "Malayalam", "mr": "Marathi",
    "nl": "Dutch", "no": "Norwegian", "pa": "Punjabi", "pl": "Polish", "pt": "Portuguese",
    "ro": "Romanian", "ru": "Russian", "sk": "Slovak", "sl": "Slovenian", "sr": "Serbian",
    "sv": "Swedish", "sw": "Swahili", "ta": "Tamil", "te": "Telugu", "th": "Thai", "tr": "Turkish",
    "uk": "Ukrainian", "ur": "Urdu", "vi": "Vietnamese", "zh": "Chinese", "zu": "Zulu",
    "bo": "Tibetan", "kk": "Kazakh", "km": "Khmer", "mn": "Mongolian", "ms": "Malay", "my": "Burmese",
    "tl": "Filipino", "ug": "Uyghur",
}


# Meaning mode (opt-in, GLYPHBRIDGE_MEANING=1): ask LLM cards to carry idioms, proverbs,
# jokes and sayings over by meaning, not word by word. Kept or dropped by golden-set numbers.
MEANING_HINT = ("If the text contains an idiom, proverb, saying, joke or figure of speech, translate it "
                "with an expression that a native speaker would use for the same meaning and tone, "
                "not word for word.")


def meaning_mode() -> bool:
    return os.environ.get("GLYPHBRIDGE_MEANING", "0") == "1"


# Context window (opt-in, GLYPHBRIDGE_CONTEXT=1): LLM cards see the preceding paragraph of
# the document, so pronouns, terms and tone carry over. Off by default: it changes the
# measured prompts, so it stays opt-in until golden-set numbers show it helps.
CONTEXT_HINT = "Context (the preceding text, for reference only; do not translate it):"
_CONTEXT = threading.local()


def context_mode() -> bool:
    return os.environ.get("GLYPHBRIDGE_CONTEXT", "0") == "1"


def set_context(mapping) -> None:
    """Text -> preceding text, for the sentences about to be translated (the engine sets it)."""
    _CONTEXT.map = dict(mapping or {})


def context_for(text: str) -> str:
    if not context_mode():
        return ""
    return (getattr(_CONTEXT, "map", None) or {}).get(text, "")


def gemma_prompt(text: str, source: str, target: str) -> str:
    """TranslateGemma's translation instruction in Gemma's chat format."""
    src, tgt = LANG_NAMES.get(source, source), LANG_NAMES.get(target, target)
    instruction = (
        f"You are a professional {src} ({source}) to {tgt} ({target}) translator. Your goal is to "
        f"accurately convey the meaning and nuances of the original {src} text while adhering to "
        f"{tgt} grammar, vocabulary, and cultural sensitivities.\n"
        + (MEANING_HINT + "\n" if meaning_mode() else "")
        + (f"{CONTEXT_HINT}\n{ctx}\n\n" if (ctx := context_for(text)) else "") +
        f"Produce only the {tgt} translation, without any additional explanations or commentary. "
        f"Please translate the following {src} text into {tgt}:\n\n\n{text}"
    )
    return f"<start_of_turn>user\n{instruction}<end_of_turn>\n<start_of_turn>model\n"


class GemmaQ4Backend(Backend):
    """TranslateGemma 4B quantized to 4 bits (GGUF, ~3 GB RAM), run with llama.cpp."""

    name = "gemma-q4"
    ram_mb = CARDS["gemma-q4"].ram_mb
    repo, revision = pinned("gemma-q4", "GLYPHBRIDGE_GEMMA_GGUF_REPO")
    filename = os.environ.get("GLYPHBRIDGE_GEMMA_GGUF_FILE", "translategemma-4b-it.Q4_K_M.gguf")

    def __init__(self, cache: ModelCache = CACHE, device: str = "cpu"):
        self.cache, self.device = cache, device
        env = os.environ.get("GLYPHBRIDGE_GEMMA_LANGS")
        self.langs = set(env.split(",")) if env else set(GEMMA_DEFAULT_LANGS)

    def enabled(self) -> bool:
        return os.environ.get("GLYPHBRIDGE_ENABLE_GEMMA") == "1" or is_installed(self.repo)

    def _load(self):
        def loader():
            try:
                from llama_cpp import Llama  # type: ignore
            except ImportError as exc:
                raise BackendUnavailable("needs: pip install 'glyphbridge[small]'") from exc
            path = os.path.join(_snapshot(self.repo, allow=[self.filename], revision=self.revision),
                                self.filename)
            return _llama(Llama, path)
        return self.cache.get(self.repo, loader, CARDS["gemma-q4"].ram_mb)

    def supports(self, source: str, target: str) -> bool:
        return self.enabled() and source in self.langs and target in self.langs

    def translate(self, texts, source, target) -> Output:
        llm = self._load()
        if llm is None:
            raise BackendUnavailable("TranslateGemma (GGUF) could not be loaded")
        out: Output = []
        for text in texts:
            res = llm(gemma_prompt(text, source, target), max_tokens=512, temperature=0.0,
                      stop=["<end_of_turn>"])
            # llama.cpp gives no cheap sequence probability here; the checker card scores it.
            out.append((res["choices"][0]["text"].strip(), None))
        return out


def _llama(Llama, path: str):
    """Open a GGUF card with llama.cpp. On CPUs the installed llama.cpp build does not
    support (Windows error 0xc000001d, illegal instruction) the card is skipped instead of
    taking the whole translation down; the other cards still work."""
    try:
        return Llama(model_path=path, n_ctx=2048, n_threads=os.cpu_count() or 2, verbose=False)
    except OSError as exc:
        raise BackendUnavailable(
            f"llama.cpp cannot run on this CPU ({exc}); the GGUF cards are skipped. "
            "Fix: build llama-cpp-python for this CPU, see README 'Older CPUs'.") from exc


# Languages Hy-MT2 was trained on (model card of tencent/Hy-MT2-1.8B).
HYMT2_LANGS = ("zh en fr pt es ja tr ru ar ko th it de vi ms id tl hi pl cs nl km my fa gu ur te mr "
               "he bn ta uk bo kk mn ug").split()


class HyMT2Q4Backend(Backend):
    """Tencent Hy-MT2 1.8B, official 4-bit GGUF (1.1 GB file, Apache 2.0), run with llama.cpp.
    36 languages. Off until installed (``glyphbridge cards install hymt2-q4``); once installed it
    is tried first, because golden-v1 measured it best for Turkish<->English (chrF 79.6 / 77.9
    against Opus-MT 75.6 / 76.8) at 2.2 GB peak RAM."""

    name = "hymt2-q4"
    ram_mb = CARDS["hymt2-q4"].ram_mb
    repo, revision = pinned("hymt2-q4", "GLYPHBRIDGE_HYMT_GGUF_REPO")
    filename = "Hy-MT2-1.8B-Q4_K_M.gguf"

    def __init__(self, cache: ModelCache = CACHE, device: str = "cpu"):
        self.cache, self.device = cache, device

    def enabled(self) -> bool:
        return os.environ.get("GLYPHBRIDGE_ENABLE_HYMT") == "1" or is_installed(self.repo)

    def _load(self):
        def loader():
            try:
                from llama_cpp import Llama  # type: ignore
            except ImportError as exc:
                raise BackendUnavailable("needs: pip install 'glyphbridge[small]'") from exc
            path = os.path.join(_snapshot(self.repo, allow=[self.filename], revision=self.revision),
                                self.filename)
            return _llama(Llama, path)
        return self.cache.get(self.repo, loader, self.ram_mb)

    def supports(self, source: str, target: str) -> bool:
        return self.enabled() and source in HYMT2_LANGS and target in HYMT2_LANGS

    @staticmethod
    def prompt(text: str, target: str) -> str:
        # The model card's default English prompt; it asks for full language names.
        hint = (MEANING_HINT + " ") if meaning_mode() else ""
        ctx = context_for(text)
        if ctx:
            hint += f"{CONTEXT_HINT}\n{ctx}\n\n"
        return (f"Translate the following text into {LANG_NAMES.get(target, target)}. {hint}Note that you should "
                f"only output the translated result without any additional explanation:\n\n{text}")

    def translate(self, texts, source, target) -> Output:
        llm = self._load()
        if llm is None:
            raise BackendUnavailable("Hy-MT2 (GGUF) could not be loaded")
        out: Output = []
        for text in texts:
            res = llm.create_chat_completion(
                messages=[{"role": "user", "content": self.prompt(text, target)}],
                max_tokens=512, temperature=0.0, repeat_penalty=1.05)
            out.append((res["choices"][0]["message"]["content"].strip(), None))
        return out


class OpusGroupBackend(OpusBackend):
    """Opus-MT multi-language group models into English, for languages without a pair
    model. Group models into English need no language tag on the source side.

    Placed after TranslateGemma and before MADLAD because golden-v1 measured, for
    Latin -> English: gemma-q4 84.9, opus-mt-itc-en 61.1, madlad-int8 38.7 (chrF)."""

    name = "opus-group"
    groups = {"la": "itc"}

    def _names(self, source: str, target: str):
        if source in self.groups and target == "en":
            return [f"Helsinki-NLP/opus-mt-{self.groups[source]}-en"]
        return []


def default_backends(cache: ModelCache = CACHE) -> List[Backend]:
    order = os.environ.get("GLYPHBRIDGE_BACKENDS",
                           "hymt2-q4,opus,gemma-q4,gemma,opus-group,madlad-int8,madlad").split(",")
    known = {"opus": OpusBackend, "gemma-q4": GemmaQ4Backend, "gemma": GemmaBackend,
             "opus-group": OpusGroupBackend, "madlad-int8": MadladInt8Backend, "madlad": MadladBackend,
             "hymt2-q4": HyMT2Q4Backend}
    return [known[n.strip()](cache) for n in order if n.strip() in known]


def names(backends: Iterable[Backend]) -> List[str]:
    return [b.name for b in backends]
