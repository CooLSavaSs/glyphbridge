# Glyphbridge

**A broad, free and offline translation toolkit that runs on an ordinary 8 GB PC — with historical scripts (Ottoman Turkish, hieroglyphs, cuneiform) as a goal, not yet a feature.**

🌐 **English** · [Türkçe](docs/i18n/README.tr.md) · [Español](docs/i18n/README.es.md) · [Français](docs/i18n/README.fr.md) · [Deutsch](docs/i18n/README.de.md) · [Português](docs/i18n/README.pt.md) · [Русский](docs/i18n/README.ru.md) · [العربية](docs/i18n/README.ar.md) · [हिन्दी](docs/i18n/README.hi.md) · [中文](docs/i18n/README.zh.md) · [日本語](docs/i18n/README.ja.md) · *[Add your language →](CONTRIBUTING.md#translate-this-readme)*

> ⚠️ **Status: early preview (0.1.0.dev0).** Text, DOCX, image (OCR) and speech translation work and are tested with real models in CI, but nothing is production-ready. Quality is measured on small test sets (see [Measured quality](#measured-quality)), not yet on full benchmarks. Items marked 📋 *Planned* do not exist yet — we'd love your help building them.
>
> **Labels used below:** ✅ **Works** — tested with real models in CI · 🧪 **Preview** — works, but limited or lightly tested · 🔬 **Experimental** — opt-in, measured but not a default · 📋 **Planned** — not built yet.

---

## Why Glyphbridge?

High-quality translation today is mostly paid, online and closed. Glyphbridge aims to be:

- **Free forever** — open source under the Apache 2.0 license. No sign-up; API keys only if you choose to expose your own server.
- **Private & offline** — everything runs on your own computer. Your documents never leave it.
- **Light** — designed to run well on an ordinary PC with **8 GB of RAM**, no GPU required.
- **Honest about quality** — every translation comes with a **confidence score**, and the goal is to publish measured quality (chrF / COMET) for each language pair instead of a single marketing number ([help wanted](https://github.com/CooLSavaSs/glyphbridge/issues)).
- **Wide language coverage** — modern text in photos, documents and speech today; historical writing systems are the long-term goal (see the roadmap).

## Features & roadmap

| Feature | Status |
|---|---|
| Text translation with a measured model router (Opus-MT, Hy-MT2, TranslateGemma, MADLAD-400) | ✅ Works |
| Model cards (install only what you need, pinned revisions, SHA-256 check), offline mode | ✅ Works |
| CLI, Python library, REST API with API keys | ✅ Works |
| Meaning checker (LaBSE) and confidence score | ✅ Works — a signal, not a quality guarantee ([see below](#about-the-confidence-score)) |
| MCP server, OpenAI-compatible endpoint | 🧪 Preview |
| DOCX translated in place (headings, lists, tables kept) | 🧪 Preview — bold/italic *inside* a paragraph is lost ([limits](#document-limits)) |
| PDF → text, TXT / MD | 🧪 Preview — PDF text layer only, no layout, no scanned PDFs |
| Images via Tesseract OCR: each line keeps its box (pixels) and OCR confidence; low confidence asks for a closer photo; `--ocr-only` writes the text to correct before translating | 🧪 Preview — not tested with real Tesseract on Windows yet |
| Live camera: `glyphbridge serve`, open `http://localhost:8080/camera` (webcam, or a phone browser over https); frames go to `POST /v1/photo` and the translation is drawn over each line | 🧪 Preview — drawing checked in a browser; not yet tried with a real camera, no box tracking between frames |
| Speech: Whisper → translation → espeak-ng (`--speak`), live microphone (`glyphbridge listen`) | 🧪 Preview — robotic voice |
| Low-RAM mode (models larger than RAM, streamed from disk) | 🔬 Experimental |
| Emotion module (tone check), built-in idiom memory, meaning mode, context window (`GLYPHBRIDGE_CONTEXT=1`: LLM cards see the preceding paragraph; not measured yet) | 🔬 Experimental |
| PDF layout, natural voices, vocabulary-trimmed cards | 📋 Planned |
| **Ottoman Turkish, printed**: page → lines → Arabic-script text (`glyphbridge ottoman page.png`, card `ota-ocr` = Azra 1-Mini 0.8B, Apache 2.0) | 🔬 Experimental — code and tests ready, **accuracy not measured by us yet** (authors report 80.2% characters on printed nesih) |
| **Ottoman Turkish**: handwriting (rika, divani), transliteration to Latin letters, modern Turkish | 📋 Planned — no openly licensed transliteration model with weights found yet |
| Sign lists from Unicode text: `glyphbridge signs "𓀀𓂀"` → Gardiner codes `A1-D58`; cuneiform → sign names (`A-ASH`) | 🔬 Experimental — listing only, not reading or translation; Unicode input only |
| **Egyptian hieroglyphs** (sign recognition in photos) and **cuneiform** (Akkadian transliteration) | 📋 Planned — research, with experts |

## Use it anywhere

Glyphbridge is built to plug into anything — your terminal, your app, your company's systems or your AI agents. The Python library, CLI, REST API, MCP server and OpenAI-compatible endpoint all work in the preview.

| Interface | Example |
|---|---|
| Python library | `glyphbridge.translate("Merhaba", to="en")` |
| Command line | `glyphbridge translate --file notes.txt --to de` |
| REST API | `glyphbridge serve` → `POST /v1/translate` (optional API key) |
| AI agents (MCP) | Use Glyphbridge as a tool from Claude and other AI assistants |
| OpenAI-compatible endpoint | `base_url=http://localhost:8080/v1`, `model="glyphbridge-en"` — existing OpenAI clients work unchanged |

```bash
curl http://localhost:8080/v1/translate \
  -H "Authorization: Bearer $GLYPHBRIDGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Merhaba dünya", "source": "tr", "target": "en"}'
# → {"translation": "Hello world", "confidence": 0.94}
```

Everything is self-hosted and free. API keys protect your server when you expose it to a network or the internet; on your own computer they are optional.

## How it works

```
 image / PDF / DOCX ──► OCR ─────────┐
 speech ─────────────► speech-to-text┤
 text ───────────────────────────────┴──► translation model ──► quality check ──► output (text / document / speech)
                                          (quantized, CPU)      (confidence score)
```

Glyphbridge builds on proven open models instead of starting from zero. A **router** picks the best model for each language pair, and a **meaning checker** compares every translation with its original: if they don't match, the sentence goes to the next model; if nothing passes, it is marked ⚠ next to the original.

| Role | Model (card) | Languages | License | RAM |
|---|---|---|---|---|
| Fast path | Opus-MT / tc-big (`opus:<src>-<tgt>`) | one pair per card | CC-BY 4.0 | ~600 MB |
| Best quality, **8 GB PCs** *(opt-in)* | TranslateGemma 4B 4-bit GGUF (`gemma-q4`) | ~55 evaluated | Gemma terms | **4.6–4.8 GB measured** (peak) |
| Rare languages, **8 GB PCs** | MADLAD-400 3B int8 CTranslate2 (`madlad-int8`) | 400+ | Apache 2.0 | **3.3–5.5 GB measured** (peak) |
| Best quality, full size *(opt-in)* | TranslateGemma 4B (`gemma`) | ~55 evaluated, ~500 pairs trained; also images | Gemma terms | **9.4 GB measured** (peak) |
| Rare languages, full size *(opt-in)* | MADLAD-400 3B (`madlad`) | 400+ (Latin, Syriac, ...) | Apache 2.0 | **6.5 GB measured** |
| Language detection | GlotLID (`lid`) | 1,600+ | Apache 2.0 | small |
| Meaning checker | LaBSE (`checker`) | 109 | Apache 2.0 | ~1 GB |
| **Best measured, 8 GB PCs** *(install to turn on)* | Tencent Hy-MT2 1.8B 4-bit GGUF (`hymt2-q4`) | 36 (incl. Turkish) | Apache 2.0 | **2.2 GB measured** (peak) |
| Emotion module *(install to turn on)* | multilingual DistilBERT sentiment (`emotion`) | multilingual | Apache 2.0 | **0.8 GB measured** |

RAM figures marked *measured* are the peak of a whole process (Python, libraries and the model) translating on CPU in CI; unmarked ones are estimates. A range means two CI runs gave different peaks; the router plans with the higher one. On an 8 GB PC the 8 GB cards fit, but leave little room for other programs.

### Measured quality

All scores are **chrF** (0–100, higher is better) against human reference translations, measured in CI. These are **small test sets**, not full benchmarks: a few dozen sentences per pair, so a difference of 2–3 points can be noise. Every row says which cards were installed, because the score depends on them.

| Test set | Size | Direction | Cards installed | Result | Run |
|---|---|---|---|---|---|
| golden-v2 | 230 sentences, 9 pairs | X→English, en→tr | all 8 GB cards, route table | tr→en **73.8**, en→tr 76.8, de→en 85.6, fr→en 80.1, es→en 88.9, ru→en 80.8, ar→en 90.5, zh→en 86.5, la→en 74.5 | CI #102 |
| golden-v2 | same | same | Opus-MT only (default install) | tr→en 73.2, en→tr 76.8, de→en 85.6, fr→en 80.1, es→en 86.9, ru→en 74.8, **ar→en 1.3 (broken, now skipped)**, zh→en 58.3, la→en 49.5 | CI #96 |
| golden-v3 | 344 sentences, 21 pairs | English→X and X→English | all 8 GB cards | Hy-MT2 leads ja→en 92.5, fa→en 86.9, ko→en 84.3, hi→en 78.1, en→ru 83.8, en→zh 50.6; Opus-MT leads en→fr 96.3, en→de 88.7, en→es 86.9, en→ar 81.3 | report only |
| golden-v3 low-resource | 9 sentences per pair | X→English | TranslateGemma 4-bit | sw→en 92.0, hi→en 88.1, fa→en 88.0, el→en 86.7 | CI #103 |
| FLORES-200 | first 20 devtest sentences × 50 languages | X→English only | Hy-MT2 + TranslateGemma 4-bit + MADLAD int8, route table | **50/50 translated, median 60.8**; best Maltese 79.0, Welsh 75.7; weakest Wolof 35.7, Yoruba 38.3, Tibetan 39.3, Quechua 39.3, Igbo 47.5 | `flores.yml` |

What the numbers taught us:

- **Small sets mislead.** On 18 sentences Hy-MT2 beat Opus-MT for tr→en (79.6 vs 75.6); on 62 sentences Opus-MT is ahead (73.2 vs 70.6). The router order comes from the larger sets.
- **Idioms are the weakest category for every model** (Opus-MT chrF 11–42). A prompt instruction ("meaning mode") moved them by only 0–1.7 chrF, so the fix is data: a translation memory (built-in idiom memory, opt-in).
- **Broken models were found and are skipped:** Opus-MT `ar-en`, and the tc-big Greek and Korean models (punctuation only). A translation with no letters now always counts as failed.
- **Latin:** MADLAD gets *Gallia est omnis divisa in partes tres* wrong; TranslateGemma 4-bit handles it, so Latin goes to `gemma-q4` when installed, otherwise to Opus-MT's Italic group model.
- **Per-card routing** (`glyphbridge/routes.py`; a card moves ahead only with ≥ 3 chrF) raised FLORES Mongolian 32.5 → 59.0, Kazakh 42.9 → 59.1, Zulu 49.5 → 59.4.
- **Not measured yet:** English→X on FLORES, more than 20 sentences per language, COMET, documents, OCR and speech accuracy.

Run them yourself: `python scripts/golden.py tests/golden/v2/tr-en.tsv` and `python scripts/flores.py --sentences 20`.

**Coverage:** with the three 8 GB cards installed (`madlad-int8`, `gemma-q4`, `hymt2-q4`), `glyphbridge languages --all` lists **493 languages** (MADLAD int8 492, TranslateGemma 4-bit 50, Hy-MT2 36). Without those cards, coverage is only the Opus-MT pairs you install. Listed does not mean good: see the FLORES weakest languages above.

**Low-RAM mode** (🔬, `GLYPHBRIDGE_LOW_RAM=1`, `pip install "glyphbridge[lowram]"`): the 9.4 GB full TranslateGemma ran under a hard **6 GB** memory cap with no swap, streaming the layers that did not fit from disk. Peak RAM 3.4 GB, both test sentences translated correctly, 44 s including loading (CI #103). Slower, but a model larger than the PC's RAM runs.

**Tested on a real 8 GB laptop** (Windows 10, a 2015-era Intel Core i5, 4 threads, no GPU, 1.6 GB RAM free at the start): Opus-MT tr→en translates in ~3 s per sentence after the first download, at 0.93 GB RAM. Two Windows problems found and fixed: the console crashed on ✓/⚠ (now printed as `?` where the console cannot show them), and a GGUF card that llama.cpp cannot run crashed the whole translation (now that card is skipped and the next one translates).

**Older CPUs:** the prebuilt `llama-cpp-python` CPU wheel stops with *illegal instruction* (Windows error `0xc000001d`) on that 2015-era Core i5, so the GGUF cards (`hymt2-q4`, `gemma-q4`) are skipped there and Opus-MT / MADLAD translate. To use them on such a CPU, build llama.cpp for it: install the Visual Studio Build Tools (C++), then `set CMAKE_ARGS=-DGGML_NATIVE=ON` and `pip install llama-cpp-python --no-binary llama-cpp-python`.

**Built-in idiom memory** (🔬, `GLYPHBRIDGE_IDIOMS=1`): 40 common Turkish↔English proverbs and idioms (folk sayings, both directions), used before any model; your own memory files override them.


### Emotion module: keep the tone

The `emotion` card reads the tone of the source and of every translation (positive, neutral or negative). If a clearly positive sentence comes back clearly negative, or the other way round, the translation is flagged (`tone changed: positive -> negative`) and the next card is tried. Results carry the source tone in `tone`. It is a card like the others: `glyphbridge cards install emotion`, about 0.8 GB RAM, loaded only while checking; `GLYPHBRIDGE_EMOTION=0` turns it off.

### Translation only

Glyphbridge does one thing: translate. It never answers, explains or chats, whatever the text says. Give it *How are you?* without a target language and it does not reply *I am fine*; it asks **which language to translate into** (in the language of the text when it can):

| Interface | Without a target language |
|---|---|
| CLI | asks interactively; with `--json` or in a pipe it prints the question and exits with code 3 |
| REST `/v1/translate` | HTTP 422, `detail.needs_target = true` and the question |
| OpenAI endpoint, model `glyphbridge` | the reply is the question; answer with a language (`de`, `German`, `Almanca`) and the previous message is translated |
| MCP `translate` | returns the question instead of a translation |

Model cards that are general language models (TranslateGemma, Hy-MT2) are only ever called with a fixed translation prompt, and the meaning checker rejects any output that is not a translation of the input.

### Translation memory: pin your own translations

Idioms and house terms are where models go wrong most often. A translation memory file fixes how a sentence or expression is translated; it is used before any model, and matching ignores case, extra spaces and the final punctuation mark:

```text
# source_lang<TAB>target_lang<TAB>source<TAB>translation
tr	en	Gözden ırak olan gönülden de ırak olur.	Out of sight, out of mind.
```

```bash
glyphbridge translate --memory idioms.tsv --to en "Gözden ırak olan gönülden de ırak olur."
export GLYPHBRIDGE_MEMORY=idioms.tsv   # for the API, MCP and Python
```

### Glossary: the same term, the same way, in the whole document

A memory pins whole sentences; a **glossary** pins *terms* inside any sentence. Wherever the term appears (with any ending: *Belediye'ye*, *vakıflar*), its fixed translation must appear in the output. A sentence that breaks the glossary is sent to the next card; if no card follows it, it is flagged (`glossary: 'Belediye' should be 'Municipality'` in `consistency_issues`) and marked for review. It checks; it cannot force a model to use the word.

```text
# source_lang<TAB>target_lang<TAB>term<TAB>translation
tr	en	Belediye	Municipality
```

```bash
glyphbridge translate --file report.docx --to en --glossary terms.tsv
export GLYPHBRIDGE_GLOSSARY=terms.tsv   # for the API, MCP and Python
```

### Model cards: only what you need runs

Every model is a **card**. Install only the cards you need; at run time only the card the current sentence needs is loaded, and cards are unloaded when the RAM budget (default: 60% of free RAM) is full. That is how Glyphbridge stays usable on an 8 GB PC.

```bash
glyphbridge cards                         # list cards and what is installed
glyphbridge cards install opus:tr-en opus:en-tr lid checker
glyphbridge cards remove madlad
GLYPHBRIDGE_OFFLINE=1 glyphbridge translate "..." --to en   # installed cards only, no downloads
```

### Roadmap: making cards smaller

The goal is to use a large model's knowledge without running all of it:

| Step | Technique | Effect |
|---|---|---|
| v0.2 ✓ | **int8 / 4-bit cards** (`madlad-int8`, `gemma-q4`): community-quantized versions of the big models | about half the RAM |
| next | **Vocabulary-trimmed cards**: a `tr-en` card keeps only the vocabulary of those two languages | even smaller RAM and disk |
| v0.3 | **Base + adapter cards**: one small shared model stays loaded; 10–50 MB LoRA adapters per language or task are swapped in | switching languages costs almost no RAM |
| v0.3 | **Distilled cards**: a large model teaches a small per-pair model | best quality per MB |
| v0.2 🔬 | **Low-RAM mode** (`GLYPHBRIDGE_LOW_RAM=1`): stream layers from disk | a 9.4 GB model ran under a 6 GB cap, slowly |

## Getting started

> This is a **preview**: text, documents (DOCX, PDF text), images (OCR) and speech work; PDF layout, natural voices and historical scripts are not done yet. Quality is measured on small test sets only — see [Measured quality](#measured-quality).

The base package is light (a few MB) and has **no translation engine by itself**. Choose a profile:

| Profile | Install | Python packages | Models (first run, needs internet once) | Good for |
|---|---|---|---|---|
| **8 GB profile** (no PyTorch) | `pip install "glyphbridge[8gb] @ git+https://github.com/CooLSavaSs/glyphbridge" --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu` | CTranslate2 23 MB + the llama.cpp CPU wheel (sizes vary by version) | `madlad-int8` ~3.0 GB, `hymt2-q4` ~1.1 GB, `gemma-q4` ~2.5 GB (install only the ones you want) | 493 languages on an 8 GB PC |
| **Opus-MT** (PyTorch) | `pip install torch --index-url https://download.pytorch.org/whl/cpu` then `pip install "glyphbridge[transformers] @ git+..."` | ~130 MB download, **~0.7 GB on disk** (PyTorch 559 MB + Transformers 120 MB, measured) | ~300 MB per language pair | fast and small per pair; works on old CPUs |
| **Everything** | `pip install torch --index-url https://download.pytorch.org/whl/cpu` then `pip install "glyphbridge[all] @ git+..."` | ~1 GB on disk | as above, plus checker ~1.9 GB, Whisper ~1 GB, … | all features |

- **Disk:** models go to the Hugging Face cache (`~/.cache/huggingface`). Plan for the model sizes above plus ~1 GB free; [docs/disk.md](docs/disk.md) has measured sizes for every card and typical sets.
- **Internet:** only to download a card the first time (`glyphbridge cards install …` does it ahead of time). After that, `GLYPHBRIDGE_OFFLINE=1` guarantees nothing is downloaded.
- **Older CPUs** (e.g. a 2015-era Core i5): the prebuilt llama.cpp wheel crashes there, so the GGUF cards (`hymt2-q4`, `gemma-q4`) are skipped — add the Opus-MT profile, or build llama.cpp yourself (see *Older CPUs* above).

```bash
# Example: the 8 GB profile with the two lightest cards
pip install "glyphbridge[8gb] @ git+https://github.com/CooLSavaSs/glyphbridge" \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
glyphbridge cards install hymt2-q4 madlad-int8
```

**Command line**

```bash
glyphbridge translate "Merhaba dünya" --from tr --to en
glyphbridge translate --file notes.txt --from tr --to de --json   # with confidence scores
glyphbridge translate --file report.docx --to en                 # -> report.en.docx
glyphbridge translate --file photo.jpg --from tr --to en          # OCR -> photo.en.txt
glyphbridge translate --file talk.mp3 --to en --speak            # speech -> talk.en.txt + talk.en.wav
glyphbridge listen --from tr --to en                              # live microphone translation
glyphbridge languages
```

The first run downloads the card it needs (or install cards ahead of time, see above); after that everything works offline. Pairs without a direct model go to MADLAD-400 or through English automatically.

**Python**

```python
import glyphbridge
result = glyphbridge.translate("Merhaba dünya", to="en", source="tr")
print(result.translation, result.confidence)
```

**REST API**

```bash
export GLYPHBRIDGE_API_KEY="choose-a-long-random-key"
glyphbridge serve --port 8080              # localhost only
glyphbridge serve --host 0.0.0.0           # network: refuses to start without an API key
```

Each client may make 120 requests per minute (`GLYPHBRIDGE_RATE_LIMIT`, 0 = unlimited). Endpoints: `GET /v1/health`, `GET /v1/languages`, `POST /v1/translate` (`text` or `texts`, `source`, `target`), and the OpenAI-compatible `GET /v1/models` + `POST /v1/chat/completions` (model `glyphbridge-<target>`). Interactive docs at `http://localhost:8080/docs`.

**AI assistants (MCP)**

```json
{ "mcpServers": { "glyphbridge": { "command": "glyphbridge", "args": ["mcp"] } } }
```

### About the confidence score

The `confidence` number (0–1) is **not the probability that the translation is correct.**

- With the `checker` card installed, it is the **meaning similarity** (LaBSE) between the original and the translation. A fluent translation that drops a negation or changes a number can still score high; a correct but freely worded one can score lower.
- Without it, it is the **model's own token probability** — how sure the model was of its words, not whether they are right.

Use it to sort what a person should look at first, not as a quality score. Measured quality per language pair is in [Measured quality](#measured-quality).

Every result (`--json`, REST, MCP, Python) also carries the signals **separately**:

| Field | Meaning |
|---|---|
| `box` | photos: where the line is in the image, (left, top, right, bottom) in pixels |
| `detected_script` | writing system of the source (ISO 15924: `Latn`, `Arab`, `Cyrl`, `Hani`, `Egyp`, …) |
| `ocr_confidence` | images only: Tesseract's mean word confidence for that line (0–1) |
| `translation_confidence` | the model's own token probability (0–1), or `null` if the card gives none |
| `similarity` | meaning similarity from the `checker` card (0–1), or `null` without it |
| `consistency_issues` | numbers or names that went missing, empty output, repeated text |
| `expert_review_required` | `true` when a check failed, the OCR confidence is below 0.70, or there was no meaning check and the model probability is below 0.50 (starting thresholds, not yet measured) |

### Document limits

- **DOCX:** each paragraph is translated as one piece. Headings, lists, tables and paragraph styles are kept, but formatting **inside** a paragraph (a bold word, an italic phrase, a link, a different font) is merged into the first run's formatting.
- **PDF:** only the **text layer** is read and the result is plain text (`.txt`). Layout, images and tables are not kept. Scanned PDFs without a text layer give no text — run them through OCR as images.
- **Images:** Tesseract OCR; accuracy depends on the photo and is not measured yet.

⭐ **Star the repo** and **watch releases** to follow progress.

## Contributing

Glyphbridge is a community project, and every kind of help counts:

- 🌍 **Translate this README** into your language — a perfect first contribution
- 🧪 Test translations in your native language and report errors
- 🐍 Write code (Python) — look for issues labeled [`good first issue`](https://github.com/CooLSavaSs/glyphbridge/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
- 📜 Help with historical scripts if you are a linguist, historian or Egyptologist

See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## License

**Glyphbridge's code** is under the [Apache License 2.0](LICENSE) — free to use, modify and share, including commercially.

**The models (cards) are not part of the code** and each keeps its own license. Installing a card means accepting its terms:

| Card | Model | License |
|---|---|---|
| `opus:<src>-<tgt>`, Opus-MT group models | Helsinki-NLP Opus-MT / tc-big | CC-BY 4.0 (attribution required) |
| `madlad`, `madlad-int8` | Google MADLAD-400 3B (int8 by Nextcloud-AI) | Apache 2.0 |
| `hymt2-q4` | Tencent Hy-MT2 1.8B GGUF | Apache 2.0 |
| `gemma`, `gemma-q4` | Google TranslateGemma 4B (4-bit community GGUF) | Gemma Terms of Use (use restrictions apply; full model is gated) |
| `lid` | GlotLID | Apache 2.0 |
| `checker` | LaBSE | Apache 2.0 |
| `emotion` | multilingual DistilBERT sentiment | Apache 2.0 |
| `whisper` | OpenAI Whisper small | MIT |
| `ota-ocr` | OttomanNLP Azra 1-Mini 0.8B (Ottoman OCR) | Apache 2.0 |
| OCR / speech output | Tesseract, espeak-ng (installed separately) | Apache 2.0 / GPL-3.0 (separate programs, not bundled) |

Not used by default because their licenses forbid commercial use: NLLB-200 (CC-BY-NC), Cohere North Small Translate (CC-BY-NC).

The **493 languages** figure counts what the 8 GB cards (`madlad-int8`, `gemma-q4`, `hymt2-q4`) cover when they are installed; a default install covers far fewer.
