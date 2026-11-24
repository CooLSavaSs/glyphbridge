"""Golden-set regression check: translate hand-picked hard sentences and measure them.

    python scripts/golden.py tests/golden/tr-en.tsv tests/golden/en-tr.tsv --min-chrf 40

For each file (named <src>-<tgt>.tsv) it reports chrF against the reference, how many
translations the checker flagged, and how many lost a number or a name. It fails when
chrF drops below --min-chrf, so a change that makes translations worse is caught.
The sentences and references are a small sanity set, not a benchmark.
"""

import argparse
import os
import sys


def load(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip() and not line.startswith("#"):
                src, ref = line.rstrip("\n").split("\t")
                rows.append((src, ref))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--min-chrf", type=float, default=40.0)
    args = ap.parse_args()

    import sacrebleu
    from glyphbridge.engine import Engine

    engine = Engine()
    lines = ["| pair | sentences | chrF | flagged | lost number/name | models used |", "|---|---|---|---|---|---|"]
    failed = False
    for path in args.files:
        pair = os.path.basename(path).rsplit(".", 1)[0]
        src_lang, tgt_lang = pair.split("-")
        rows = load(path)
        results = engine.translate_batch([s for s, _ in rows], target=tgt_lang, source=src_lang)
        hyps = [r.translation for r in results]
        chrf = sacrebleu.corpus_chrf(hyps, [[ref for _, ref in rows]]).score
        flagged = sum(r.flagged for r in results)
        lost = sum(bool(r.issues) for r in results)
        models = ", ".join(sorted({r.model for r in results}))
        lines.append(f"| {pair} | {len(rows)} | {chrf:.1f} | {flagged} | {lost} | {models} |")
        for (src, ref), r in zip(rows, results):
            mark = "⚠" if r.flagged else " "
            print(f"{mark} [{pair}] {src}\n    -> {r.translation}\n    ref {ref}  {('; '.join(r.issues))}", flush=True)
        if chrf < args.min_chrf:
            failed = True
            print(f"FAIL {pair}: chrF {chrf:.1f} < {args.min_chrf}", flush=True)
    table = "\n".join(lines)
    print("\n" + table)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("### Golden set\n\n" + table + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
