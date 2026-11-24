# Glyphbridge work plan

The order in which the core team works. Every step ends with a measurement in CI or a test;
nothing is marked done on a guess. `[x]` done, `[ ]` open. Issues welcome on any step.

## A. Measure first
- [x] A1. golden-v1 sanity set (31 sentences, 3 pairs)
- [x] A2. golden-v2 (230 sentences, 9 pairs), first scores in README
- [x] A3. Fix what golden-v2 found: Arabic tc-big model, German false alarms, result cache
- [x] A4. Regression thresholds per pair from the measured golden-v2 scores (CI fails on a real drop)
- [ ] A5. English → X directions (en-de, en-fr, en-es, en-ru, en-ar, en-zh) in golden-v3
- [ ] A6. More languages in golden-v3: Persian, Japanese, Korean, Hindi, Swahili, Greek
- [ ] A7. Low-resource probe set (Yoruba, Hausa, Amharic, Uzbek, Syriac, Latin) for MADLAD and Hy-MT2

## B. Route by measurement
- [x] B1. Measured route table: for each pair, the card that scored best on golden-v2 goes first
      (`glyphbridge/routes.py`, from CI #96/#97 results, tested)
- [ ] B2. Re-measure the default chain with the route table; keep it only if every pair is ≥ before

## C. Meaning, idioms and tone
- [ ] C1. "Meaning" prompt for LLM cards: translate idioms and sayings by their target-language
      equivalent, not word by word; measure the idioms category before/after
- [ ] C2. Idiom memory seed: a small public-domain idiom file per language pair (opt-in)
- [ ] C3. Emotion module beyond polarity (joy, anger, sadness, irony) only if a small permissive
      multilingual model measures well

## D. Large models on 8 GB (cards and layers)
- [ ] D1. `--low-ram` mode: memory-map GGUF weights from disk so a model larger than free RAM
      still runs (slower); CI job under a hard 8 GB memory limit
- [ ] D2. Measure speed and quality of a larger card in `--low-ram` mode vs the 4-bit cards
- [ ] D3. Document disk needs per card set ("minimal", "8 GB best", "16 GB best")

## E. Every language
- [ ] E1. `glyphbridge languages --all`: every language any installed card supports, with the card
- [ ] E2. Language names in many languages for the "which language?" question
- [ ] E3. Historical scripts research track (Ottoman Turkish OCR, Syriac, Akkadian, hieroglyphs):
      data sources, licences, first OCR baseline

## F. Product
- [ ] F1. Real Windows test on a CPU-only PC (install, CLI, API)
- [ ] F2. PDF layout, natural voices (licence decisions pending)
- [ ] F3. Release 0.1.0 on PyPI
