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

import math
import os
import threading
from collections import OrderedDict
from typing import Iterable, List, Optional, Sequence, Tuple

from .cards import CARDS, OPUS_RAM_MB, is_installed, offline

Output = List[Tuple[str, float]]  # (translation, model probability 0–1)


class BackendUnavailable(RuntimeError):
    """The backend cannot load its model (not installed, gated, offline, ...)."""


class ModelCache:
    """Process-wide cache of loaded cards with a RAM budget.

    Only the cards a sentence needs are loaded. When the estimated RAM of the
    loaded cards would exceed the budget, the least recently used card is unloaded
    first. A single card larger than the budget is still allowed on its own.
    """

    def __init__(self, budget_mb: Optional[int] = None, max_models: Optional[int] = None):
        from .cards import ram_budget_mb
        self.budget_mb = budget_mb if budget_mb is not None else ram_budget_mb()
        self.max_models = max_models or int(os.environ.get("GLYPHBRIDGE_MAX_MODELS", "3"))
        self._items: "OrderedDict[str, Tuple[object, int]]" = OrderedDict()
        self._failed: set = set()
        self._lock = threading.Lock()

    @property
    def used_mb(self) -> int:
        return sum(ram for _, ram in self._items.values())

    def _evict_for(self, ram_mb: int) -> None:
        while self._items and (self.used_mb + ram_mb > self.budget_mb or len(self._items) >= self.max_models):
            self._items.popitem(last=False)
        import gc
        gc.collect()

    def get(self, key: str, loader, ram_mb: int = 0):
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key][0]
            if key in self._failed:
                return None
            self._evict_for(ram_mb)
        try:
            value = loader()
        except BackendUnavailable:
            with self._lock:
                self._failed.add(key)
            return None
        with self._lock:
            self._items[key] = (value, ram_mb)
        return value


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
class OpusBackend(Backend):
    """Direct Opus-MT models; tries the larger tc-big model first."""

    name = "opus"
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
            except (ImportError, OSError, ValueError) as exc:
                raise BackendUnavailable(str(exc)) from exc
        return self.cache.get(name, loader, OPUS_RAM_MB)

    def _model_for(self, source: str, target: str):
        for tpl in self.templates:
            name = tpl.format(src=source, tgt=target)
            loaded = self._load_named(name)
            if loaded is not None:
                return name, loaded
        return None, None

    def supports(self, source: str, target: str) -> bool:
        return self._model_for(source, target)[0] is not None

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
    model_id = os.environ.get("GLYPHBRIDGE_MADLAD_MODEL", "google/madlad400-3b-mt")

    def __init__(self, cache: ModelCache = CACHE, device: str = "cpu"):
        self.cache, self.device = cache, device

    def _load(self):
        def loader():
            try:
                from transformers import AutoTokenizer, T5ForConditionalGeneration  # type: ignore
                import torch  # type: ignore
                tok = AutoTokenizer.from_pretrained(self.model_id)
                model = T5ForConditionalGeneration.from_pretrained(
                    self.model_id, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True).to(self.device).eval()
                return tok, model
            except (ImportError, OSError, ValueError) as exc:
                raise BackendUnavailable(str(exc)) from exc
        return self.cache.get(self.model_id, loader, CARDS["madlad"].ram_mb)

    def supports(self, source: str, target: str) -> bool:
        # MADLAD takes the target as a "<2xx>" tag and reads any source language.
        if os.environ.get("GLYPHBRIDGE_DISABLE_MADLAD") == "1":
            return False
        return not offline() or is_installed(self.model_id)

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
GEMMA_DEFAULT_LANGS = (
    "ar bg bn ca cs da de el en es et fa fi fr gu he hi hr hu id it ja kn ko lt lv ml mr "
    "nl no pa pl pt ro ru sk sl sr sv sw ta te th tr uk ur vi zh zu"
).split()


class GemmaBackend(Backend):
    """TranslateGemma (opt-in: accept the Gemma terms on Hugging Face, log in, then
    ``glyphbridge cards install gemma``)."""

    name = "gemma"
    model_id = os.environ.get("GLYPHBRIDGE_GEMMA_MODEL", "google/translategemma-4b-it")

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
                proc = AutoProcessor.from_pretrained(self.model_id)
                model = AutoModelForImageTextToText.from_pretrained(
                    self.model_id, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True).to(self.device).eval()
                return proc, model
            except (ImportError, OSError, ValueError) as exc:
                raise BackendUnavailable(str(exc)) from exc
        return self.cache.get(self.model_id, loader, CARDS["gemma"].ram_mb)

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


def default_backends(cache: ModelCache = CACHE) -> List[Backend]:
    order = os.environ.get("GLYPHBRIDGE_BACKENDS", "opus,gemma,madlad").split(",")
    known = {"opus": OpusBackend, "gemma": GemmaBackend, "madlad": MadladBackend}
    return [known[n.strip()](cache) for n in order if n.strip() in known]


def names(backends: Iterable[Backend]) -> List[str]:
    return [b.name for b in backends]
