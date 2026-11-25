"""Command-line interface.

    glyphbridge translate "Merhaba dünya" --to en
    glyphbridge translate --file notes.txt --from tr --to de
    glyphbridge translate --file report.docx --to en        # -> report.en.docx
    glyphbridge translate --file photo.jpg --from tr --to en  # OCR, -> photo.en.txt
    glyphbridge translate --file talk.mp3 --to en --speak     # speech -> talk.en.txt + talk.en.wav
    glyphbridge listen --from tr --to en                      # live microphone translation
    echo "Hola" | glyphbridge translate --to en --json
    glyphbridge serve --port 8080 --api-key "$GLYPHBRIDGE_API_KEY"
    glyphbridge mcp
    glyphbridge languages
    glyphbridge cards install opus:tr-en
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from . import __version__
from .engine import SUPPORTED_LANGUAGES, TranslationError, get_engine


DOC_EXTS = {".docx", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp",
            ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".opus", ".webm"}


def _cmd_translate_file(args: argparse.Namespace) -> int:
    from .documents import translate_file
    from .speech import AUDIO_EXTS, translate_audio
    try:
        if os.path.splitext(args.file)[1].lower() in AUDIO_EXTS:
            speak_out = os.path.splitext(args.file)[0] + f".{args.to}.wav" if args.speak else None
            out, results = translate_audio(args.file, target=args.to, source=args.source,
                                           out=args.output, speak_out=speak_out)
            if speak_out:
                print(f"\u2713 speech -> {speak_out}")
        else:
            out, results = translate_file(args.file, target=args.to, source=args.source, out=args.output)
    except (TranslationError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    flagged = [r for r in results if r.flagged]
    print(f"\u2713 {len(results)} segments translated -> {out}")
    if flagged:
        print(f"\u26a0 {len(flagged)} segments have low confidence; check them against the original.",
              file=sys.stderr)
    return 0


def _ensure_target(args: argparse.Namespace, sample: str) -> int:
    """Glyphbridge only translates: without --to it asks for the target language."""
    if args.to:
        return 0
    from .engine import ask_target, parse_language
    ask = ask_target(sample[:500])
    if sys.stdin.isatty() and not args.json:
        answer = input(f"{ask['question']} ({ask['question_en']}) > ")
        args.to = parse_language(answer) or answer.strip().lower()
        return 0
    if args.json:
        print(json.dumps(ask, ensure_ascii=False))
    else:
        print(f"{ask['question']} ({ask['question_en']}) -> use --to <language code>", file=sys.stderr)
    return 3


def _cmd_translate(args: argparse.Namespace) -> int:
    if getattr(args, "ocr_only", False):
        if not args.file:
            print("error: --ocr-only needs --file <image>", file=sys.stderr)
            return 2
        from .documents import ocr_only
        out, regions = ocr_only(args.file, source=args.source, out=args.output)
        if args.json:
            print(json.dumps({"output": out, "lines": regions}, ensure_ascii=False, indent=2))
        else:
            print(f"{len(regions)} OCR lines -> {out}\nCorrect the text, then: "
                  f"glyphbridge translate --file {out} --to <language>", file=sys.stderr)
        return 0
    if args.file and not args.to:
        rc = _ensure_target(args, os.path.basename(args.file))
        if rc:
            return rc
    if args.file and (args.output or os.path.splitext(args.file)[1].lower() in DOC_EXTS):
        return _cmd_translate_file(args)
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            text = fh.read()
    elif args.text:
        text = " ".join(args.text)
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("Give text, --file, or pipe text in.", file=sys.stderr)
        return 2
    rc = _ensure_target(args, text)
    if rc:
        return rc

    # Translate paragraph by paragraph so long documents keep their layout.
    paragraphs = text.split("\n")
    idx = [i for i, p in enumerate(paragraphs) if p.strip()]
    try:
        results = get_engine().translate_batch([paragraphs[i] for i in idx], target=args.to, source=args.source)
    except TranslationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    out = list(paragraphs)
    flagged = []
    for i, r in zip(idx, results):
        out[i] = r.translation
        if r.flagged:
            flagged.append((paragraphs[i], r))

    if args.json:
        print(json.dumps({"translation": "\n".join(out), "results": [r.to_dict() for r in results]},
                         ensure_ascii=False, indent=2))
    else:
        print("\n".join(out))
        known = [r.confidence for r in results if r.confidence is not None]
        if args.show_confidence and known:
            low = min(known)
            print(f"\n[confidence: lowest {low:.2f}]", file=sys.stderr)
        for original, r in flagged:
            why = "; ".join(r.issues) or f"low confidence {r.confidence or 0:.2f}"
            print(f"\u26a0 {why}: {original!r} -> {r.translation!r}", file=sys.stderr)
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    key = args.api_key or os.environ.get("GLYPHBRIDGE_API_KEY")
    if args.host not in ("127.0.0.1", "localhost", "::1") and not key:
        print("Refusing to listen on a network address without an API key. "
              "Set --api-key or GLYPHBRIDGE_API_KEY.", file=sys.stderr)
        return 2
    try:
        import uvicorn  # type: ignore
        from .server import create_app
    except ImportError:
        print("The API server needs: pip install 'glyphbridge[server]'", file=sys.stderr)
        return 1
    uvicorn.run(create_app(api_key=key), host=args.host, port=args.port)
    return 0


def _cmd_mcp(_: argparse.Namespace) -> int:
    from .mcp_server import run
    run()
    return 0


def _cmd_cards(args: argparse.Namespace) -> int:
    from . import cards
    if args.action in (None, "list"):
        have = set(cards.installed_cards())
        print(f"RAM budget: {cards.ram_budget_mb()} MB  (set GLYPHBRIDGE_RAM_BUDGET_MB to change)\n")
        for c in cards.CARDS.values():
            mark = "\u2713" if c.id in have else " "
            print(f"[{mark}] {c.id:<11} RAM ~{c.ram_mb:>5} MB  disk {c.disk:<8} {c.license:<12} {c.title}")
            if c.note:
                print(f"    {'':<11} {c.note}")
        opus = sorted(x for x in have if x.startswith(cards.OPUS_PREFIX))
        tick = "\u2713" if opus else " "
        print(f"\n[{tick}] opus:<src>-<tgt>  RAM ~{cards.OPUS_RAM_MB} MB each, disk ~300 MB each"
              f"  installed: {', '.join(opus) or 'none'}")
        return 0
    if not args.cards:
        print("Name at least one card, e.g. opus:tr-en", file=sys.stderr)
        return 2
    for cid in args.cards:
        try:
            if args.action == "install":
                print(f"Installing {cid} ...")
                cards.install(cid)
                print(f"\u2713 {cid}")
            elif args.action == "verify":
                files = cards.verify(cid)
                print(f"\u2713 {cid}: SHA-256 OK for {', '.join(files)}" if files else f"{cid}: no pinned checksums")
            else:
                freed = cards.remove(cid)
                print(f"Removed {cid} ({freed / 1e6:.0f} MB freed)" if freed else f"{cid} was not installed")
        except Exception as exc:
            print(f"error: {cid}: {exc}", file=sys.stderr)
            return 1
    return 0


def _cmd_listen(args: argparse.Namespace) -> int:
    from .speech import listen
    print(f"Listening ({args.seconds:g}s chunks) - press Ctrl+C to stop.", file=sys.stderr)
    try:
        listen(target=args.to, source=args.source, seconds=args.seconds)
    except KeyboardInterrupt:
        pass
    except (RuntimeError, TranslationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_languages(args: argparse.Namespace) -> int:
    if not getattr(args, "all", False):
        for code, name in SUPPORTED_LANGUAGES.items():
            print(f"{code}\t{name}")
        return 0
    from . import coverage
    rows = coverage.table()
    for code, cards_ in rows:
        print(f"{code}\t{SUPPORTED_LANGUAGES.get(code, '')}\t{','.join(cards_)}")
    print(f"{len(rows)} languages covered by the installed cards", file=sys.stderr)
    if not rows:
        print("No cards installed yet: glyphbridge cards install hymt2-q4 madlad-int8", file=sys.stderr)
    return 0


def _cmd_ottoman(args) -> int:
    from . import ottoman
    lines = ottoman.read_page(args.image, lines_already=args.line)
    out = args.output or os.path.splitext(args.image)[0] + ".ota.txt"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(ottoman.to_text(lines))
    if args.json:
        print(json.dumps({"output": out, "note": ottoman.REVIEW_NOTE, "lines": [line.to_dict() for line in lines]},
                         ensure_ascii=False, indent=2))
    else:
        print(ottoman.to_text(lines))
        print(f"\n{len(lines)} lines -> {out}\n! {ottoman.REVIEW_NOTE}", file=sys.stderr)
    return 0


def _cmd_signs(args) -> int:
    from . import ancient
    text = " ".join(args.text)
    found = ancient.signs(text)
    if args.json:
        print(json.dumps([s.to_dict() for s in found], ensure_ascii=False, indent=2))
    elif found:
        print(ancient.sign_list(text))
    if not found:
        print("No hieroglyph or cuneiform characters found (Unicode input needed; photos are not "
              "recognised yet).", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="glyphbridge", description="Free, offline translation toolkit.")
    p.add_argument("--version", action="version", version=f"glyphbridge {__version__}")
    p.add_argument("--profile", choices=["fast", "balanced", "quality", "low-ram"],
                   help="Speed/RAM/quality trade-off (or GLYPHBRIDGE_PROFILE); your own settings still win")
    sub = p.add_subparsers(dest="command", required=True)

    t = sub.add_parser("translate", help="Translate text or a text file")
    t.add_argument("text", nargs="*", help="Text to translate")
    t.add_argument("--file", "-f", help="Translate a file: .txt, .md, .docx, .pdf, an image (OCR) or audio (speech)")
    t.add_argument("--speak", action="store_true", help="For audio input: also write the translation as speech (.wav)")
    t.add_argument("--output", "-o", help="Where to write the translated file (default: name.<lang>.ext)")
    t.add_argument("--from", dest="source", default="auto", help="Source language code (default: auto)")
    t.add_argument("--to", "-t", help="Target language code (asked for if missing)")
    t.add_argument("--json", action="store_true", help="Print JSON with confidence scores")
    t.add_argument("--ocr-only", action="store_true",
                   help="Images: only write the OCR text (<image>.ocr.txt) so you can correct it, then translate that")
    t.add_argument("--show-confidence", action="store_true", help="Print the lowest confidence to stderr")
    t.add_argument("--memory", action="append", default=[],
                   help="Translation memory file (TSV: source_lang, target_lang, source, translation); repeatable")
    t.add_argument("--glossary", action="append", default=[],
                   help="Glossary file (TSV: source_lang, target_lang, term, translation): keeps terms "
                        "consistent across the document; repeatable")
    t.set_defaults(func=_cmd_translate)

    s = sub.add_parser("serve", help="Run the REST API server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8080)
    s.add_argument("--api-key", help="Require this API key (or set GLYPHBRIDGE_API_KEY)")
    s.set_defaults(func=_cmd_serve)

    m = sub.add_parser("mcp", help="Run the MCP server for AI assistants (stdio)")
    m.set_defaults(func=_cmd_mcp)

    li = sub.add_parser("listen", help="Live translation from the microphone")
    li.add_argument("--from", dest="source", default="auto", help="Spoken language (default: auto)")
    li.add_argument("--to", "-t", required=True, help="Target language code")
    li.add_argument("--seconds", type=float, default=5.0, help="Length of each recorded chunk")
    li.set_defaults(func=_cmd_listen)

    c = sub.add_parser("cards", help="List, install, verify or remove model cards")
    c.add_argument("action", nargs="?", choices=["list", "install", "remove", "verify"])
    c.add_argument("cards", nargs="*", help="Card ids, e.g. opus:tr-en madlad gemma lid checker")
    c.set_defaults(func=_cmd_cards)

    o = sub.add_parser("ottoman", help="Experimental: OCR a printed Ottoman Turkish page (Arabic script)")
    o.add_argument("image", help="Page image (or a single line image with --line)")
    o.add_argument("--line", action="store_true", help="The image is already one text line")
    o.add_argument("--output", "-o", help="Write the text here (default: <image>.ota.txt)")
    o.add_argument("--json", action="store_true", help="Print lines with boxes and review flags as JSON")
    o.set_defaults(func=_cmd_ottoman)

    sg = sub.add_parser("signs", help="Experimental: list Egyptian hieroglyph (Gardiner) or cuneiform sign codes "
                                      "in Unicode text - not a reading or translation")
    sg.add_argument("text", nargs="+", help="Unicode hieroglyph or cuneiform text")
    sg.add_argument("--json", action="store_true", help="One entry per sign with code point and kind")
    sg.set_defaults(func=_cmd_signs)

    lang = sub.add_parser("languages", help="List core language codes (--all: every language installed cards cover)")
    lang.add_argument("--all", action="store_true", help="Every language any installed card covers, with the cards")
    lang.set_defaults(func=_cmd_languages)
    return p


def _safe_console() -> None:
    """Windows consoles often use a code page (cp1252, cp857...) that cannot show ✓ or ⚠ or
    every script we translate. Print what they cannot show as '?' instead of crashing."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: Optional[List[str]] = None) -> int:
    _safe_console()
    args = build_parser().parse_args(argv)
    from . import profiles
    if args.profile:
        os.environ["GLYPHBRIDGE_PROFILE"] = args.profile
    profiles.apply_from_env()
    if getattr(args, "memory", None):
        existing = [p for p in os.environ.get("GLYPHBRIDGE_MEMORY", "").split(os.pathsep) if p]
        os.environ["GLYPHBRIDGE_MEMORY"] = os.pathsep.join(existing + args.memory)
    if getattr(args, "glossary", None):
        existing = [p for p in os.environ.get("GLYPHBRIDGE_GLOSSARY", "").split(os.pathsep) if p]
        os.environ["GLYPHBRIDGE_GLOSSARY"] = os.pathsep.join(existing + args.glossary)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
