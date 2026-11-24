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


def _cmd_translate(args: argparse.Namespace) -> int:
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
        if args.show_confidence and results:
            low = min(r.confidence for r in results)
            print(f"\n[confidence: lowest {low:.2f}]", file=sys.stderr)
        for original, r in flagged:
            print(f"\u26a0 low confidence ({r.confidence:.2f}): {original!r} -> {r.translation!r}", file=sys.stderr)
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
            print(f"[{mark}] {c.id:<8} RAM ~{c.ram_mb:>5} MB  disk {c.disk:<8} {c.license:<12} {c.title}")
            if c.note:
                print(f"    {'':<8} {c.note}")
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


def _cmd_languages(_: argparse.Namespace) -> int:
    for code, name in SUPPORTED_LANGUAGES.items():
        print(f"{code}\t{name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="glyphbridge", description="Free, offline translation for every script.")
    p.add_argument("--version", action="version", version=f"glyphbridge {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    t = sub.add_parser("translate", help="Translate text or a text file")
    t.add_argument("text", nargs="*", help="Text to translate")
    t.add_argument("--file", "-f", help="Translate a file: .txt, .md, .docx, .pdf, an image (OCR) or audio (speech)")
    t.add_argument("--speak", action="store_true", help="For audio input: also write the translation as speech (.wav)")
    t.add_argument("--output", "-o", help="Where to write the translated file (default: name.<lang>.ext)")
    t.add_argument("--from", dest="source", default="auto", help="Source language code (default: auto)")
    t.add_argument("--to", "-t", required=True, help="Target language code")
    t.add_argument("--json", action="store_true", help="Print JSON with confidence scores")
    t.add_argument("--show-confidence", action="store_true", help="Print the lowest confidence to stderr")
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

    c = sub.add_parser("cards", help="List, install or remove model cards")
    c.add_argument("action", nargs="?", choices=["list", "install", "remove"])
    c.add_argument("cards", nargs="*", help="Card ids, e.g. opus:tr-en madlad gemma lid checker")
    c.set_defaults(func=_cmd_cards)

    lang = sub.add_parser("languages", help="List core language codes")
    lang.set_defaults(func=_cmd_languages)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
