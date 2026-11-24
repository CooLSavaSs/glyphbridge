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
| **v0.1** | Text translation, first 10–20 languages, command line + simple UI, quantized model (int8) | 🚧 In progress |
| **v0.2** | Translate text in **images** (OCR) and **documents** (PDF, DOCX) while keeping the layout; confidence score filter | 📋 Planned |
| **v0.3** | **Speech** translation: speech → text → translation → speech | 📋 Planned |
| **v0.4** | **Ottoman Turkish**: printed & handwritten (rika, divani) OCR, transliteration, modern Turkish | 📋 Planned |
| **Experimental** | **Egyptian hieroglyphs** and **cuneiform** (Akkadian, Sumerian) — in collaboration with researchers | 🔬 Research |

## Use it anywhere (planned)

Glyphbridge is built to plug into anything — your terminal, your app, your company's systems or your AI agents:

| Interface | Example |
|---|---|
| Python library | `glyphbridge.translate("Merhaba", to="en")` |
| Command line | `glyphbridge translate file.pdf --to de` |
| REST API | `glyphbridge serve` → `POST /v1/translate` (optional API key) |
| AI agents (MCP) | Use Glyphbridge as a tool from Claude and other AI assistants |
| OpenAI-compatible endpoint | Plug into existing AI tools without code changes |

```bash
# planned REST API example
curl http://localhost:8080/v1/translate \
  -H "Authorization: Bearer $GLYPHBRIDGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Merhaba dünya", "source": "tr", "target": "en"}'
# → {"translation": "Hello world", "confidence": 0.94}
```

Everything is self-hosted and free. API keys protect your server when you expose it to a network or the internet; on your own computer they are optional.

## How it works (planned architecture)

```
 image / PDF / DOCX ──► OCR ─────────┐
 speech ─────────────► speech-to-text┤
 text ───────────────────────────────┴──► translation model ──► quality check ──► output (text / document / speech)
                                          (quantized, CPU)      (confidence score)
```

Glyphbridge builds on proven open models instead of starting from zero, and fine-tunes them for translation only:

- **Translation:** MADLAD-400 / Opus-MT, run with CTranslate2 (int8)
- **OCR:** PaddleOCR / Tesseract
- **Speech:** Whisper (speech-to-text), Piper (text-to-speech)
- **Quality estimation:** COMET-based confidence scores

## Getting started

Not ready yet — the first release (v0.1) is in progress. ⭐ **Star the repo** and **watch releases** to be notified.

## Contributing

Glyphbridge is a community project, and every kind of help counts:

- 🌍 **Translate this README** into your language — a perfect first contribution
- 🧪 Test translations in your native language and report errors
- 🐍 Write code (Python) — look for issues labeled [`good first issue`](https://github.com/CooLSavaSs/glyphbridge/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
- 📜 Help with historical scripts if you are a linguist, historian or Egyptologist

See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## License

[Apache License 2.0](LICENSE) — free to use, modify and share, including commercially.
