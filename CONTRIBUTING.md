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
2. **Describe it** in `glyphbridge/cards.py`: id, title, Hugging Face repo, pinned revision,
   SHA-256 of the weight files, RAM in MB, disk size and license. Measure RAM if you can and
   say so (`"6.5 GB measured"`).
3. **Implement a backend** in `glyphbridge/backends.py`: subclass `Backend`, set `name` and
   `ram_mb`, implement `supports(source, target)` and `translate(texts, source, target)`
   returning `(translation, probability or None)` pairs. Load the model inside a `loader`
   passed to `self.cache.get(key, loader, ram_mb)` so the RAM budget can unload it, and raise
   `BackendUnavailable` when it cannot load.
4. **Register it** in `default_backends()` at the right place in the order (fast/small first).
5. **Test it**: a unit test with a fake model in `tests/`, and a real-model check in
   `scripts/smoke_cards.py` that runs in the *Cards (real models)* workflow.

Cards must work on a CPU-only PC; a card that needs more than ~4 GB RAM should be opt-in.

### Card checklist

A pull request that adds or changes a card fills in this table in its description:

| Item | What to give |
|---|---|
| Source | Hugging Face repo and the pinned 40-character `revision` |
| Checksum | SHA-256 of the main weight files (`sha256=` in `cards.py`; `glyphbridge cards verify <id>` must pass) |
| License | License of the weights *and* of the base model it was converted from |
| RAM | Peak RAM **measured** on CPU while translating (not only the file size) |
| Pairs | Which language pairs or how many languages it covers |
| Speed | CPU latency for one ~20-word sentence, and the CPU it was measured on |
| Quality | `scripts/golden.py` result (chrF per category) against the current default card |
| 8 GB fit | Does it run next to the OS and a browser on an 8 GB PC? If not, it is opt-in |

The golden set is versioned (`tests/golden/v1` = golden-v1). Do not change a released set;
add new sentences in a new version so scores stay comparable.

### How cards are chosen

The router is a fixed, readable order (fast/small cards first, then larger ones, with the
quality checker sending failed sentences on). It is covered by tests. A learned or
"smart" router will only be considered once there are benchmark numbers that show the
fixed order is wrong for some language pairs.

## Reporting a translation error

Open an issue with:
- source language and target language
- the original text
- the translation you got and what it should be

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).
