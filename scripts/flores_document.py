"""Document-length multilingual benchmark using aligned FLORES-200 devtest text.

Builds one approximately N-English-word-equivalent document per language pair,
translates it in paragraph-sized chunks, and scores the complete document against
the aligned human reference. English-word-equivalent length keeps the page size
comparable across scripts whose word segmentation differs.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import tarfile

import sacrebleu
from glyphbridge.engine import Engine
from flores import LANGS, archive, read


def english_equivalent_document(tar: tarfile.TarFile, code: str, target_words: int,
                                direction: str, paragraph_sentences: int = 3):
    """Return aligned source/reference paragraphs reaching target English words."""
    # FLORES-200 devtest contains 1,012 aligned sentences.
    en = read(tar, "eng_Latn", 1012)
    other = read(tar, code, 1012)
    if direction == "x-en":
        source_lines, reference_lines = other, en
    else:
        source_lines, reference_lines = en, other

    src_paragraphs, ref_paragraphs = [], []
    english_words = 0
    for start in range(0, min(len(en), len(other)), paragraph_sentences):
        end = min(start + paragraph_sentences, len(en), len(other))
        src = " ".join(source_lines[start:end]).strip()
        ref = " ".join(reference_lines[start:end]).strip()
        if not src or not ref:
            continue
        src_paragraphs.append(src)
        ref_paragraphs.append(ref)
        # The English side is the common yardstick for every script/language.
        english_words += len(en[start:end][0].split()) if end - start == 1 else sum(
            len(line.split()) for line in en[start:end])
        if english_words >= target_words:
            break
    return src_paragraphs, ref_paragraphs, english_words


def evaluate_language(engine: Engine, tar: tarfile.TarFile, code: str,
                      words: int, direction: str):
    src_lang = LANGS[code]
    source, reference, english_words = english_equivalent_document(
        tar, code, words, direction)
    if not source:
        return {"language": code, "error": "No aligned FLORES text"}

    source_code, target_code = ((src_lang, "en") if direction == "x-en"
                                else ("en", src_lang))
    started = time.perf_counter()
    results = engine.translate_batch(source, target=target_code, source=source_code)
    elapsed = time.perf_counter() - started
    hypotheses = [r.translation for r in results]
    hyp = [" ".join(hypotheses)]
    ref = [" ".join(reference)]
    chrf = sacrebleu.corpus_chrf(hyp, [ref]).score
    bleu = sacrebleu.corpus_bleu(hyp, [ref]).score
    source_chars = sum(len(p) for p in source)
    source_words = sum(len(p.split()) for p in source)
    return {
        "language": code,
        "source": source_code,
        "target": target_code,
        "english_word_equivalent": english_words,
        "source_whitespace_words": source_words,
        "source_characters": source_chars,
        "paragraphs": len(source),
        "chrf": round(chrf, 2),
        "bleu": round(bleu, 2),
        "seconds": round(elapsed, 2),
        "seconds_per_english_100_words": round(elapsed * 100 / max(english_words, 1), 2),
        "english_words_per_second": round(english_words / max(elapsed, 0.001), 2),
        "flagged": sum(bool(r.flagged) for r in results),
        "cards": sorted({r.model.split(":")[0] for r in results}),
        "error": None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--langs", nargs="*", default=list(LANGS))
    parser.add_argument("--words", type=int, default=500,
                        help="English-word-equivalent document length")
    parser.add_argument("--direction", choices=("x-en", "en-x", "both"), default="both")
    parser.add_argument("--json", default="document-benchmark.json")
    args = parser.parse_args()
    if args.words < 1:
        parser.error("--words must be positive")
    directions = ("x-en", "en-x") if args.direction == "both" else (args.direction,)
    report = {
        "dataset": "FLORES-200 devtest",
        "length_definition": "approximately N English-word-equivalent words",
        "requested_words": args.words,
        "directions": {},
        "backend_setting": os.environ.get("GLYPHBRIDGE_BACKENDS", "default"),
    }
    engine = Engine()
    with tarfile.open(archive(), "r:gz") as tar:
        for direction in directions:
            rows = []
            print(f"\n## {direction} — approximately {args.words} English-word-equivalent words",
                  flush=True)
            for code in args.langs:
                if code not in LANGS:
                    rows.append({"language": code, "error": "Unknown FLORES language code"})
                    continue
                try:
                    row = evaluate_language(engine, tar, code, args.words, direction)
                except Exception as exc:  # one unsupported language must not abort the batch
                    row = {"language": code, "error": f"{type(exc).__name__}: {exc}"}
                rows.append(row)
                if row.get("error"):
                    print(f"| {code} | unavailable/error | {row['error']} |", flush=True)
                else:
                    print("| {language} | {english_word_equivalent} | {cards} | "
                          "{chrf} | {bleu} | {seconds}s | {flagged} |".format(
                              **{**row, "cards": ", ".join(row["cards"])}), flush=True)
            scored = [r["chrf"] for r in rows if "chrf" in r]
            report["directions"][direction] = {
                "languages_requested": len(args.langs),
                "languages_scored": len(scored),
                "median_chrf": round(statistics.median(scored), 2) if scored else None,
                "results": rows,
            }
    with open(args.json, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(f"\nJSON report: {args.json}", flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"\n# Multilingual document benchmark — {args.words} English-word-equivalent words\n")
            for direction, result in report["directions"].items():
                handle.write(f"\n## {direction}\n\n")
                handle.write(f"Scored {result['languages_scored']}/{result['languages_requested']} languages; ")
                handle.write(f"median chrF: {result['median_chrf']}\n\n")
                handle.write("| Language | English-word equivalent | Cards | chrF | BLEU | Total time | Flagged |\n")
                handle.write("|---|---:|---|---:|---:|---:|---:|\n")
                for row in result["results"]:
                    if row.get("error"):
                        handle.write(f"| {row['language']} | — | — | — | — | — | — |\n")
                    else:
                        handle.write(f"| {row['language']} | {row['english_word_equivalent']} | "
                                     f"{', '.join(row['cards'])} | {row['chrf']} | {row['bleu']} | "
                                     f"{row['seconds']}s | {row['flagged']} |\n")


if __name__ == "__main__":
    main()
