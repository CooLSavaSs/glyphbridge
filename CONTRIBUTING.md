# Contributing to Glyphbridge

Thank you for helping build free translation for every language! 🌍
All contributions are welcome — code, translations, testing, documentation and research.

## Ways to help

| You are… | You can… |
|---|---|
| A native speaker of any language | Translate the README, test translations, report errors |
| A Python developer | Pick an issue labeled `good first issue` or `help wanted` |
| An ML / NLP person | Help with model selection, quantization, fine-tuning and evaluation |
| A linguist, historian or Egyptologist | Help with Ottoman Turkish, hieroglyphs and cuneiform datasets |

## Translate this README

1. Copy `README.md` to `docs/i18n/README.<code>.md`, where `<code>` is the [ISO 639-1 language code](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) (for example `README.ko.md` for Korean).
2. Translate the text. Keep links, code and the feature table structure unchanged.
3. Add your language to the 🌐 language bar at the top of `README.md` and of every file in `docs/i18n/`.
4. Open a pull request titled `docs(i18n): add <Language> README`.

Already have a translation in your language? Native-speaker corrections are just as valuable — please open a pull request.

## Code contributions

1. Fork the repository and create a branch: `git checkout -b feature/short-description`
2. Keep pull requests small and focused on one change.
3. Describe **what** you changed and **why** in the pull request.
4. Be kind and respectful in all discussions.

## Adding a model card

A *card* is one model Glyphbridge can load on demand. To add one:

1. **Check the license first.** Code and weights must allow commercial use and redistribution
   (Apache-2.0, MIT, BSD, CC-BY...). Non-commercial (CC-BY-NC), region-restricted or
   copyleft (GPL/AGPL) models are not accepted as default cards.
2. **Describe it** in `glyphbridge/cards.py`: id, title, Hugging Face repo, estimated RAM in MB,
   disk size and license. Measure RAM if you can and say so (`"6.5 GB measured"`).
3. **Implement a backend** in `glyphbridge/backends.py`: subclass `Backend`, set `name` and
   `ram_mb`, implement `supports(source, target)` and `translate(texts, source, target)`
   returning `(translation, probability or None)` pairs. Load the model inside a `loader`
   passed to `self.cache.get(key, loader, ram_mb)` so the RAM budget can unload it, and raise
   `BackendUnavailable` when it cannot load.
4. **Register it** in `default_backends()` at the right place in the order (fast/small first).
5. **Test it**: a unit test with a fake model in `tests/`, and a real-model check in
   `scripts/smoke_cards.py` that runs in the *Cards (real models)* workflow.

Cards must work on a CPU-only PC; a card that needs more than ~4 GB RAM should be opt-in.

## Reporting a translation error

Open an issue with:
- source language and target language
- the original text
- the translation you got and what it should be

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).
