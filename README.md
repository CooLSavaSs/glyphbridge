# Glyphbridge

**Free, offline, open-source translation for every script — from modern languages to Ottoman Turkish, hieroglyphs and cuneiform.**

🌐 **English** · [Türkçe](docs/i18n/README.tr.md) · [Español](docs/i18n/README.es.md) · [Français](docs/i18n/README.fr.md) · [Deutsch](docs/i18n/README.de.md) · [Português](docs/i18n/README.pt.md) · [Русский](docs/i18n/README.ru.md) · [العربية](docs/i18n/README.ar.md) · [हिन्दी](docs/i18n/README.hi.md) · [中文](docs/i18n/README.zh.md) · [日本語](docs/i18n/README.ja.md) · *[Add your language →](CONTRIBUTING.md#translate-this-readme)*

> ⚠️ **Status: early development.** Glyphbridge is being built in the open. Features below marked *planned* do not exist yet — we'd love your help building them.

---

## Why Glyphbridge?

High-quality translation today is mostly paid, online and closed. Glyphbridge aims to be:

- **Free forever** — open source under the Apache 2.0 license. No sign-up; API keys only if you choose to expose your own server.
- **Private & offline** — everything runs on your own computer. Your documents never leave it.
- **Light** — designed to run well on an ordinary PC with **8 GB of RAM**, no GPU required.
- **Honest about quality** — every translation comes with a **confidence score**, and we publish measured quality (COMET / chrF) for each language pair instead of a single marketing number.
- **For every script** — not just modern text, but text in photos, documents, speech, and historical writing systems.

## Features & roadmap

| Version | Feature | Status |
|---|---|---|
| **v0.1** | Text translation with a model router (Opus-MT → TranslateGemma → MADLAD-400), meaning checker, install-only-what-you-need model cards, CLI, REST API with API keys, MCP server | 🧪 Preview |
| **v0.2** | Translate text in **images** (OCR) and **documents** (PDF, DOCX) while keeping the layout; confidence score filter | 📋 Planned |
| **v0.3** | **Speech** translation: speech → text → translation → speech | 📋 Planned |
| **v0.4** | **Ottoman Turkish**: printed & handwritten (rika, divani) OCR, transliteration, modern Turkish | 📋 Planned |
| **Experimental** | **Egyptian hieroglyphs** and **cuneiform** (Akkadian, Sumerian) — in collaboration with researchers | 🔬 Research |

## Use it anywhere

Glyphbridge is built to plug into anything — your terminal, your app, your company's systems or your AI agents. The Python library, CLI, REST API and MCP server work in the v0.1 preview; the OpenAI-compatible endpoint is planned.

| Interface | Example |
|---|---|
| Python library | `glyphbridge.translate("Merhaba", to="en")` |
| Command line | `glyphbridge translate --file notes.txt --to de` |
| REST API | `glyphbridge serve` → `POST /v1/translate` (optional API key) |
| AI agents (MCP) | Use Glyphbridge as a tool from Claude and other AI assistants |
| OpenAI-compatible endpoint *(planned)* | Plug into existing AI tools without code changes |

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

| Role | Model (card) | Languages | License | RAM (est.) |
|---|---|---|---|---|
| Fast path | Opus-MT / tc-big (`opus:<src>-<tgt>`) | one pair per card | CC-BY 4.0 | ~600 MB |
| Best quality *(opt-in)* | TranslateGemma 4B (`gemma`) | ~55 evaluated, ~500 pairs trained; also images | Gemma terms | ~9 GB today, 4-bit card planned |
| Rare languages | MADLAD-400 3B (`madlad`) | 400+ (Latin, Syriac, ...) | Apache 2.0 | ~6.5 GB today, int8 card planned |
| Language detection | GlotLID (`lid`) | 1,600+ | Apache 2.0 | small |
| Meaning checker | LaBSE (`checker`) | 109 | Apache 2.0 | ~1 GB |

Not used by default because their licenses forbid commercial use or exclude regions: NLLB-200 (CC-BY-NC), Cohere North Small Translate (CC-BY-NC), Tencent Hy-MT2 (community license, excludes the EU).

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
| v0.2 | **Vocabulary-trimmed + int8 cards**: a `tr-en` card keeps only the vocabulary of those two languages | much smaller RAM and disk, near-identical quality |
| v0.3 | **Base + adapter cards**: one small shared model stays loaded; 10–50 MB LoRA adapters per language or task are swapped in | switching languages costs almost no RAM |
| v0.3 | **Distilled cards**: a large model teaches a small per-pair model | best quality per MB |
| later | **`--low-ram` mode**: stream layers from disk one at a time | runs very large models on small PCs, but slowly |

## Getting started

> v0.1 is a **preview**: text translation works; images, documents, speech and historical scripts come in later versions.

```bash
# CPU-only PyTorch keeps the install small
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install "glyphbridge[all] @ git+https://github.com/CooLSavaSs/glyphbridge"
```

**Command line**

```bash
glyphbridge translate "Merhaba dünya" --from tr --to en
glyphbridge translate --file notes.txt --from tr --to de --json   # with confidence scores
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

Endpoints: `GET /v1/health`, `GET /v1/languages`, `POST /v1/translate` (`text` or `texts`, `source`, `target`). Interactive docs at `http://localhost:8080/docs`.

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
