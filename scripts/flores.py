"""Measure X -> English quality on FLORES-200 devtest (human translations, CC-BY-SA 4.0).

    python scripts/flores.py --sentences 20 --json flores.json
    python scripts/flores.py --langs yor_Latn hau_Latn --sentences 50

The official archive is downloaded once from Meta's server into ~/.cache/glyphbridge
and read as plain text; nothing from it is executed or stored in this repository.
For every language the same first N devtest sentences are translated into English
with the current engine (route table and installed cards) and scored with chrF.
A language no installed card supports is reported as "no card".
"""

import argparse
import json
import os
import sys
import tarfile
import time
import urllib.request

URL = "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz"

# FLORES code -> Glyphbridge (ISO 639) code. A spread of families, scripts and resource levels.
LANGS = {
    "tur_Latn": "tr", "deu_Latn": "de", "fra_Latn": "fr", "spa_Latn": "es", "rus_Cyrl": "ru",
    "arb_Arab": "ar", "zho_Hans": "zh", "jpn_Jpan": "ja", "kor_Hang": "ko", "hin_Deva": "hi",
    "pes_Arab": "fa", "ell_Grek": "el", "heb_Hebr": "he", "vie_Latn": "vi", "ind_Latn": "id",
    "ben_Beng": "bn", "urd_Arab": "ur", "tam_Taml": "ta", "tel_Telu": "te", "tha_Thai": "th",
    "swh_Latn": "sw", "yor_Latn": "yo", "hau_Latn": "ha", "ibo_Latn": "ig", "amh_Ethi": "am",
    "som_Latn": "so", "zul_Latn": "zu", "xho_Latn": "xh", "kin_Latn": "rw", "wol_Latn": "wo",
    "uzn_Latn": "uz", "kaz_Cyrl": "kk", "kir_Cyrl": "ky", "tat_Cyrl": "tt", "azj_Latn": "az",
    "uig_Arab": "ug", "khk_Cyrl": "mn", "bod_Tibt": "bo", "khm_Khmr": "km", "mya_Mymr": "my",
    "npi_Deva": "ne", "sin_Sinh": "si", "kmr_Latn": "ku", "ckb_Arab": "ckb", "pbt_Arab": "ps",
    "quy_Latn": "qu", "grn_Latn": "gn", "eus_Latn": "eu", "cym_Latn": "cy", "mlt_Latn": "mt",
}


def archive() -> str:
    cache = os.path.join(os.path.expanduser("~"), ".cache", "glyphbridge")
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, "flores200_dataset.tar.gz")
    if not os.path.exists(path):
        print(f"downloading {URL}", flush=True)
        urllib.request.urlretrieve(URL, path + ".part")
        os.replace(path + ".part", path)
    return path


def read(tar: tarfile.TarFile, code: str, n: int):
    member = f"flores200_dataset/devtest/{code}.devtest"
    with tar.extractfile(member) as fh:  # read as text only, never extracted to disk
        return [fh.readline().decode("utf-8").rstrip("\n") for _ in range(n)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--langs", nargs="*", default=list(LANGS))
    ap.add_argument("--sentences", type=int, default=20)
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    import sacrebleu
    from glyphbridge.engine import Engine

    engine = Engine()
    rows, report = [], {"source": "FLORES-200 devtest", "sentences": args.sentences, "langs": {}}
    with tarfile.open(archive(), "r:gz") as tar:
        refs = read(tar, "eng_Latn", args.sentences)
        for code in args.langs:
            iso = LANGS[code]
            src = read(tar, code, args.sentences)
            t0 = time.time()
            try:
                res = engine.translate_batch(src, target="en", source=iso)
            except Exception as exc:  # noqa: BLE001 - one missing language must not stop the rest
                print(f"SKIP {code}: {exc}", flush=True)
                rows.append(f"| {code} | {iso} | no card | – | – |")
                report["langs"][code] = {"iso": iso, "error": str(exc)}
                continue
            chrf = round(sacrebleu.corpus_chrf([r.translation for r in res], [refs]).score, 1)
            cards = sorted({r.model.split(":")[0] for r in res})
            secs = round((time.time() - t0) / len(src), 1)
            flagged = sum(bool(r.flagged) for r in res)
            rows.append(f"| {code} | {iso} | {', '.join(cards)} | **{chrf}** | {flagged} | {secs} s |")
            report["langs"][code] = {"iso": iso, "chrf": chrf, "cards": cards, "flagged": flagged,
                                     "seconds_per_sentence": secs}
            print(rows[-1], flush=True)

    scored = [v["chrf"] for v in report["langs"].values() if "chrf" in v]
    head = (f"### FLORES-200 devtest, X→English, first {args.sentences} sentences per language\n\n"
            f"{len(scored)} of {len(args.langs)} languages translated; median chrF "
            f"{sorted(scored)[len(scored) // 2] if scored else '–'}\n\n"
            "| FLORES | code | cards | chrF | flagged | time/sentence |\n|---|---|---|---|---|---|\n")
    table = head + "\n".join(rows)
    print("\n" + table)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(table + "\n\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
