"""Golden-set regression check: translate hand-picked hard sentences and measure them.

    python scripts/golden.py tests/golden/v1/tr-en.tsv tests/golden/v1/en-tr.tsv --min-chrf 40
    python scripts/golden.py tests/golden/v1/la-en.tsv:0 --json golden.json
    python scripts/golden.py tests/golden/v2/de-en.tsv:0 tests/golden/v2/zh-en.tsv:0

Each file is named <src>-<tgt>.tsv and has the columns category, source, reference.
The set is versioned by folder (v1 = golden-v1): never edit a released set in place,
copy it to v2 so scores stay comparable over time.

For every file and every category it reports chrF against the reference, how many
translations the checker flagged and how many lost a number or a name. The run fails
when a file's chrF drops below its threshold (--min-chrf, or path:N to set one per
file; :0 means report only). This is a small sanity set, not a benchmark.
"""

import argparse
import json
import os
import sys
from collections import OrderedDict

VERSION_HINT = "golden-v1"


def load(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip() and not line.startswith("#"):
                parts = line.rstrip("\n").split("\t")
                if len(parts) == 2:
                    parts = ["general"] + parts
                category, src, ref = parts
                rows.append((category, src, ref))
    return rows


def split_spec(spec, default):
    path, _, threshold = spec.rpartition(":")
    if path and threshold.replace(".", "", 1).isdigit():
        return path, float(threshold)
    return spec, default


def score(rows, results):
    import sacrebleu
    hyps = [r.translation for r in results]
    refs = [ref for _, _, ref in rows]
    return {
        "sentences": len(rows),
        "chrf": round(sacrebleu.corpus_chrf(hyps, [refs]).score, 1),
        "flagged": sum(bool(r.flagged) for r in results),
        "lost_number_or_name": sum(bool(r.issues) for r in results),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="<src>-<tgt>.tsv, optionally path:min_chrf")
    ap.add_argument("--min-chrf", type=float, default=40.0)
    ap.add_argument("--json", help="write per-file and per-category results here")
    args = ap.parse_args(argv)

    from glyphbridge.engine import Engine

    engine = Engine()
    report = OrderedDict(version=VERSION_HINT, files=OrderedDict())
    lines = ["| pair | category | sentences | chrF | flagged | lost number/name |",
             "|---|---|---|---|---|---|"]
    failed = False
    for spec in args.files:
        path, threshold = split_spec(spec, args.min_chrf)
        version = os.path.basename(os.path.dirname(os.path.abspath(path)))
        if version.startswith("v"):
            report["version"] = "golden-" + version
        pair = os.path.basename(path).rsplit(".", 1)[0]
        src_lang, tgt_lang = pair.split("-")
        rows = load(path)
        results = engine.translate_batch([s for _, s, _ in rows], target=tgt_lang, source=src_lang)

        total = score(rows, results)
        total["models"] = sorted({r.model for r in results})
        total["threshold"] = threshold
        by_cat = OrderedDict()
        for cat in dict.fromkeys(c for c, _, _ in rows):
            idx = [i for i, (c, _, _) in enumerate(rows) if c == cat]
            by_cat[cat] = score([rows[i] for i in idx], [results[i] for i in idx])
            s = by_cat[cat]
            lines.append(f"| {pair} | {cat} | {s['sentences']} | {s['chrf']:.1f} | {s['flagged']} | "
                         f"{s['lost_number_or_name']} |")
        lines.append(f"| **{pair}** | **all** ({', '.join(total['models'])}) | {total['sentences']} | "
                     f"**{total['chrf']:.1f}** | {total['flagged']} | {total['lost_number_or_name']} |")
        total["categories"] = by_cat
        total["sentences_detail"] = [
            {"category": c, "source": s, "reference": ref, "translation": r.translation,
             "model": r.model, "flagged": r.flagged, "issues": r.issues}
            for (c, s, ref), r in zip(rows, results)]
        report["files"][pair] = total

        for (cat, src, ref), r in zip(rows, results):
            mark = "⚠" if r.flagged else " "
            print(f"{mark} [{pair}/{cat}] {src}\n    -> {r.translation}\n    ref {ref}  "
                  f"{'; '.join(r.issues)}", flush=True)
        if threshold and total["chrf"] < threshold:
            failed = True
            print(f"FAIL {pair}: chrF {total['chrf']:.1f} < {threshold}", flush=True)

    table = "\n".join(lines)
    print(f"\n{report['version']}\n" + table)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"### Golden set ({report['version']})\n\n" + table + "\n\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
