"""Measure the speed profiles: latency, peak RAM and quality, each in its own process.

    python scripts/profiles_bench.py tests/golden/v2/tr-en.tsv tests/golden/v2/en-tr.tsv
    python scripts/profiles_bench.py --profiles fast low-ram --json profiles.json tests/golden/v2/tr-en.tsv

Every profile runs in a fresh Python process, so its settings and its peak RAM are its own.
Reported per profile: model load + first sentence (s), seconds per sentence afterwards,
peak RAM of the whole process (MB, sampled every 50 ms) and chrF on the given golden files.
Uses only cards that are already installed when GLYPHBRIDGE_OFFLINE=1 is set.
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time

PROFILES = ["fast", "balanced", "quality", "low-ram"]


def _peak_rss(stop: threading.Event, out: list) -> None:
    import psutil
    proc, peak = psutil.Process(), 0
    while not stop.is_set():
        peak = max(peak, proc.memory_info().rss)
        stop.wait(0.05)
    out.append(max(peak, proc.memory_info().rss))


def child(profile: str, files) -> dict:
    """Run inside the profile's own process."""
    os.environ["GLYPHBRIDGE_PROFILE"] = profile
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from golden import load  # same file format as the golden sets
    stop, peak = threading.Event(), []
    watcher = threading.Thread(target=_peak_rss, args=(stop, peak), daemon=True)
    watcher.start()
    from glyphbridge.engine import Engine
    engine = Engine()
    hyps, refs, first, times, flagged = [], [], None, [], 0
    for path in files:
        src, tgt = os.path.basename(path).rsplit(".", 1)[0].split("-", 1)
        for _, text, ref in load(path):
            t0 = time.perf_counter()
            r = engine.translate(text, target=tgt, source=src)
            dt = time.perf_counter() - t0
            if first is None:
                first = dt
            else:
                times.append(dt)
            hyps.append(r.translation)
            refs.append(ref)
            flagged += bool(r.flagged)
    stop.set()
    watcher.join()
    import sacrebleu
    return {"profile": profile, "sentences": len(hyps),
            "first_s": round(first or 0, 1),
            "per_sentence_s": round(sum(times) / len(times), 2) if times else None,
            "peak_ram_mb": round(peak[0] / 1e6) if peak else None,
            "chrf": round(sacrebleu.corpus_chrf(hyps, [refs]).score, 1) if hyps else None,
            "flagged": flagged}


def table(rows) -> str:
    head = ("| profile | sentences | load + first (s) | per sentence (s) | peak RAM (MB) | chrF | flagged |\n"
            "|---|---|---|---|---|---|---|\n")
    lines = []
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['profile']} | – | – | – | – | – | error: {r['error'][:80]} |")
        else:
            lines.append(f"| {r['profile']} | {r['sentences']} | {r['first_s']} | {r['per_sentence_s']} | "
                         f"{r['peak_ram_mb']} | **{r['chrf']}** | {r['flagged']} |")
    return head + "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="golden files named <src>-<tgt>.tsv")
    ap.add_argument("--profiles", nargs="*", default=PROFILES, choices=PROFILES)
    ap.add_argument("--json")
    ap.add_argument("--child", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if args.child:
        print("RESULT " + json.dumps(child(args.child, args.files)), flush=True)
        return 0

    rows = []
    for profile in args.profiles:
        env = {k: v for k, v in os.environ.items() if k != "GLYPHBRIDGE_PROFILE"}
        proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--child", profile, *args.files],
                              env=env, capture_output=True, text=True, encoding="utf-8")
        found = [line[7:] for line in proc.stdout.splitlines() if line.startswith("RESULT ")]
        rows.append(json.loads(found[-1]) if found else
                    {"profile": profile, "error": (proc.stderr.strip().splitlines() or ["no output"])[-1]})
        print(table(rows[-1:]).splitlines()[-1], flush=True)
    out = "### Speed profiles\n\n" + table(rows)
    print("\n" + out)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=2)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(out + "\n\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
