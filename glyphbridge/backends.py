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

from .cards import CARDS, OPUS_RAM_MB, _cached_repos, is_installed, offline, pinned

Output = List[Tuple[str, Optional[float]]]  # (translation, model probability 0–1, or None if unknown)


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

    def _names(self, source: str, target: str):
        return [tpl.format(src=source, tgt=target) for tpl in self.templates]

    def _model_for(self, source: str, target: str):
        cached = _cached_repos() if offline() else None
        for name in self._names(source, target):
            if cached is not None and name not in cached:
                continue  # offline: only installed pair cards
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
                model = AutoModelForImageTextToText.from_pretrained(
                    self.model_id, revision=self.revision, torch_dtype=torch.bfloat16,
                    low_cpu_mem_usage=True).to(self.device).eval()
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


def gemma_prompt(text: str, source: str, target: str) -> str:
    """TranslateGemma's translation instruction in Gemma's chat format."""
    src, tgt = LANG_NAMES.get(source, source), LANG_NAMES.get(target, target)
    instruction = (
        f"You are a professional {src} ({source}) to {tgt} ({target}) translator. Your goal is to "
        f"accurately convey the meaning and nuances of the original {src} text while adhering to "
        f"{tgt} grammar, vocabulary, and cultural sensitivities.\n"
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
            return Llama(model_path=path, n_ctx=2048, n_threads=os.cpu_count() or 2, verbose=False)
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
            return Llama(model_path=path, n_ctx=2048, n_threads=os.cpu_count() or 2, verbose=False)
        return self.cache.get(self.repo, loader, self.ram_mb)

    def supports(self, source: str, target: str) -> bool:
        return self.enabled() and source in HYMT2_LANGS and target in HYMT2_LANGS

    @staticmethod
    def prompt(text: str, target: str) -> str:
        # The model card's default English prompt; it asks for full language names.
        return (f"Translate the following text into {LANG_NAMES.get(target, target)}. Note that you should "
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
