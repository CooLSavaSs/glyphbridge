# Glyphbridge

**Free, offline, open-source translation for every script — from modern languages to Ottoman Turkish, hieroglyphs and cuneiform.**

🌐 **English** · [Türkçe](docs/i18n/README.tr.md) · [Español](docs/i18n/README.es.md) · [Français](docs/i18n/README.fr.md) · [Deutsch](docs/i18n/README.de.md) · [Português](docs/i18n/README.pt.md) · [Русский](docs/i18n/README.ru.md) · [العربية](docs/i18n/README.ar.md) · [हिन्दी](docs/i18n/README.hi.md) · [中文](docs/i18n/README.zh.md) · [日本語](docs/i18n/README.ja.md) · *[Add your language →](CONTRIBUTING.md#translate-this-readme)*

> ⚠️ **Status: early preview (0.1.0.dev0).** Text, DOCX, image (OCR) and speech translation work and are tested with real models in CI, but nothing is production-ready and quality has not been benchmarked yet. Items marked *planned* or *research* do not exist yet — we'd love your help building them.

---

## Why Glyphbridge?

High-quality translation today is mostly paid, online and closed. Glyphbridge aims to be:

- **Free forever** — open source under the Apache 2.0 license. No sign-up; API keys only if you choose to expose your own server.
- **Private & offline** — everything runs on your own computer. Your documents never leave it.
- **Light** — designed to run well on an ordinary PC with **8 GB of RAM**, no GPU required.
- **Honest about quality** — every translation comes with a **confidence score**, and the goal is to publish measured quality (chrF / COMET) for each language pair instead of a single marketing number ([help wanted](https://github.com/CooLSavaSs/glyphbridge/issues)).
- **For every script** — not just modern text, but text in photos, documents, speech, and historical writing systems.

## Features & roadmap

| Version | Feature | Status |
|---|---|---|
| **v0.1** | Text translation with a model router (Opus-MT → TranslateGemma → MADLAD-400), meaning checker, install-only-what-you-need model cards, CLI, REST API with API keys, MCP server | 🧪 Preview |
| **v0.2** | **Documents**: DOCX translated in place (headings, lists, tables kept), PDF text layer → text, TXT/MD; **images** via Tesseract OCR. Next: PDF layout, trimmed int8 cards | 🧪 Partly in preview |
| **v0.3** | **Speech**: Whisper speech-to-text → translation → espeak-ng speech (`--speak`); live microphone mode (`glyphbridge listen`). Next: natural voices | 🧪 Preview |
| **v0.4** | **Ottoman Turkish**: printed & handwritten (rika, divani) OCR, transliteration, modern Turkish | 📋 Planned |
| **Experimental** | **Egyptian hieroglyphs** and **cuneiform** (Akkadian, Sumerian) — in collaboration with researchers | 🔬 Research |

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

**Quality so far** (golden-v1, a small hand-made sanity set, not a benchmark): Opus-MT reaches chrF **75.6** for Turkish→English and **76.8** for English→Turkish. Names, numbers, negation and technical text score well; idioms are weak (chrF 22–28) and are the next thing to improve. For Latin, MADLAD gets the regression case *Gallia est omnis divisa in partes tres* wrong (chrF 38.7), while TranslateGemma 4-bit (`gemma-q4`) scores **84.9**, so Latin now goes to `gemma-q4` when it is installed. For Turkish, `gemma-q4` scored lower than Opus-MT (68.6 / 64.4), so Opus-MT stays first. Without `gemma-q4`, Latin goes to the Apache-licensed Opus-MT Italic group model (`opus-mt-itc-en`, chrF **61.1**). Numbers like these, not guesses, decide the router order.

**golden-v2** (230 sentences, 9 pairs, report only; first run, CI #96). chrF per pair:

| pair | Opus-MT (default) | Hy-MT2 4-bit | TranslateGemma 4-bit |
|---|---|---|---|
| tr→en (62) | **73.2** | 70.6 | 69.0 |
| en→tr (45) | **76.8** | **76.8** | 68.7 |
| de→en (15) | **85.6** | 80.1 | – |
| fr→en (15) | **80.1** | 76.5 | – |
| es→en (15) | 86.9 | **88.9** | – |
| ru→en (15) | 74.8 | **80.8** | – |
| ar→en (13) | **1.3 (broken)** | **90.5** | – |
| zh→en (15) | 58.3 | **86.5** | – |
| la→en (25) | 49.5 (opus-group) | – | **75.1** |

What the larger set changed: on golden-v1 (18 sentences) Hy-MT2 beat Opus-MT for tr→en (79.6 vs 75.6); on 62 sentences Opus-MT is ahead (73.2 vs 70.6), so small sets mislead. Two real bugs surfaced: the default Opus-MT `ar-en` path returns unusable output (all 13 sentences flagged), and the name/number check raises false alarms on German (14 of 15 flagged, because German capitalises every noun). Idioms stay the weakest category for every model (chrF 11–42 for Opus-MT).

**Measured route table** (`glyphbridge/routes.py`): for each measured pair the best card goes first (Opus-MT for Turkish, German and French; Hy-MT2 for Spanish, Russian, Arabic and Chinese; TranslateGemma 4-bit for Latin). With all 8 GB cards installed, golden-v2 gives tr→en **73.8**, en→tr 76.8, de→en 85.6, fr→en 80.1, es→en 88.9, ru→en 80.8, ar→en 90.5, zh→en 86.5, la→en 74.5: every pair at or above the best single card, Latin 0.6 below `gemma-q4` alone. CI fails if the default chain drops ~8 chrF below its first measured score.

**golden-v3** (344 sentences, 21 pairs; report only) adds English→German/French/Spanish/Russian/Arabic/Chinese and Persian, Japanese, Korean, Hindi, Swahili, Greek→English. Hy-MT2 leads for ja→en (92.5), fa→en (86.9), ko→en (84.3), hi→en (78.1), en→ru (83.8) and en→zh (50.6); Opus-MT for en→fr (96.3), en→de (88.7), en→es (86.9) and en→ar (81.3). The route table includes these pairs. Two more broken Opus-MT tc-big models turned up (Greek, Korean: punctuation only) and are skipped; a translation with no letters is now always treated as failed. **Meaning mode** (`GLYPHBRIDGE_MEANING=1`, an idiom instruction for LLM cards) moved idiom scores by only 0–1.7 chrF and lowered zh→en by 2.5, so it stays opt-in: idioms need data (a translation memory), not a prompt.

**Low-resource probe** (golden-v3, 9 sentences per pair, CI #103): TranslateGemma 4-bit scores sw→en **92.0**, hi→en **88.1**, fa→en **88.0**, el→en **86.7**; MADLAD int8 70.7 / – / 66.0 / 79.2. The route table now sends these pairs to `gemma-q4` first.

**Coverage:** with the 8 GB cards installed, `glyphbridge languages --all` lists **493 languages** (MADLAD int8 492, TranslateGemma 4-bit 50, Hy-MT2 36).

**Low-RAM mode works** (`GLYPHBRIDGE_LOW_RAM=1`, `pip install "glyphbridge[lowram]"`): the 9.4 GB full TranslateGemma ran under a hard **6 GB** memory cap with no swap, streaming the layers that did not fit from disk. Peak RAM 3.4 GB, both test sentences translated correctly, 44 s including loading (CI #103). Slower, but a model larger than the PC's RAM runs.

**Tested on a real 8 GB laptop** (Windows 10, a 2015-era Intel Core i5, 4 threads, no GPU, 1.6 GB RAM free at the start): Opus-MT tr→en translates in ~3 s per sentence after the first download, at 0.93 GB RAM. Two Windows problems found and fixed: the console crashed on ✓/⚠ (now printed as `?` where the console cannot show them), and a GGUF card that llama.cpp cannot run crashed the whole translation (now that card is skipped and the next one translates).

**Older CPUs:** the prebuilt `llama-cpp-python` CPU wheel stops with *illegal instruction* (Windows error `0xc000001d`) on that 2015-era Core i5, so the GGUF cards (`hymt2-q4`, `gemma-q4`) are skipped there and Opus-MT / MADLAD translate. To use them on such a CPU, build llama.cpp for it: install the Visual Studio Build Tools (C++), then `set CMAKE_ARGS=-DGGML_NATIVE=ON` and `pip install llama-cpp-python --no-binary llama-cpp-python`.

**Built-in idiom memory** (`GLYPHBRIDGE_IDIOMS=1`): 40 common Turkish↔English proverbs and idioms (folk sayings, both directions), used before any model; your own memory files override them.

Not used by default because their licenses forbid commercial use or exclude regions: NLLB-200 (CC-BY-NC), Cohere North Small Translate (CC-BY-NC). (Tencent Hy-MT2 used to be in this list; it is Apache 2.0 now and is the `hymt2-q4` card.)

**Hy-MT2** (Tencent, the most-liked translation model on Hugging Face) is the best card measured so far for Turkish↔English: chrF **79.6** / **77.9** against Opus-MT's 75.6 / 76.8, idioms 46.8 against 28.4, at 2.2 GB peak RAM. Once installed (`glyphbridge cards install hymt2-q4`) it is tried first.

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
| later | **`--low-ram` mode**: stream layers from disk one at a time | runs very large models on small PCs, but slowly |

## Getting started

> This is a **preview**: text, documents (DOCX, PDF text), images (OCR) and speech work; PDF layout, natural voices and historical scripts are not done yet. Quality has not been benchmarked.

```bash
# CPU-only PyTorch keeps the install small
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install "glyphbridge[all] @ git+https://github.com/CooLSavaSs/glyphbridge"
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

**About the confidence score:** with the `checker` card installed it is the meaning similarity between original and translation (0–1); without it, the model's own token probability. Both are signals, not measured quality scores — published per-language-pair benchmarks are planned.

⭐ **Star the repo** and **watch releases** to follow progress.

## Contributing

Glyphbridge is a community project, and every kind of help counts:

- 🌍 **Translate this README** into your language — a perfect first contribution
- 🧪 Test translations in your native language and report errors
- 🐍 Write code (Python) — look for issues labeled [`good first issue`](https://github.com/CooLSavaSs/glyphbridge/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
- 📜 Help with historical scripts if you are a linguist, historian or Egyptologist

See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## License

[Apache License 2.0](LICENSE) — free to use, modify and share, including commercially.
