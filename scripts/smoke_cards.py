"""Real-model smoke tests for Glyphbridge cards. Used by .github/workflows/cards.yml.

    python scripts/smoke_cards.py lid checker ocr pipeline speech
    python scripts/smoke_cards.py madlad
"""

import os
import sys
import tempfile
import time


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'} {name} {detail}", flush=True)
    if not cond:
        check.failed = True


check.failed = False


def test_lid():
    from glyphbridge import lid
    for text, want in [("Bugün hava çok güzel, parka gidelim mi?", "tr"),
                       ("Das ist ein wirklich schöner Tag am See.", "de"),
                       ("Это очень красивый город на берегу моря.", "ru"),
                       ("Gallia est omnis divisa in partes tres.", "la")]:
        got = lid.detect(text)
        check("lid", got == want, f"{want} -> {got}")


def test_checker():
    from glyphbridge.checker import Checker
    c = Checker()
    good, bad = c.similarity(["Bugün hava çok güzel.", "Bugün hava çok güzel."],
                             ["The weather is very nice today.", "The stock market fell sharply."])
    check("checker good pair passes", c.passes(good), f"similarity={good}")
    check("checker wrong pair fails", not c.passes(bad), f"similarity={bad}")


def test_ocr():
    from PIL import Image, ImageDraw, ImageFont
    from glyphbridge.documents import ocr_image
    img = Image.new("RGB", (900, 160), "white")
    try:  # a font with Turkish letters (ü, ş, ğ); the built-in default font has none
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 64)
    except OSError:
        font = ImageFont.load_default(size=64)
    ImageDraw.Draw(img).text((20, 40), "Merhaba dünya", fill="black", font=font)
    path = os.path.join(tempfile.mkdtemp(), "ocr.png")
    img.save(path)
    text = ocr_image(path, "tr")
    check("ocr reads Turkish text incl. ü", "Merhaba dünya" in text, repr(text.strip()))


def test_pipeline():
    from glyphbridge.engine import Engine
    r = Engine().translate("Bugün hava çok güzel.", target="en", source="tr")
    check("pipeline tr->en with checker", bool(r.translation) and r.similarity is not None and not r.flagged,
          f"{r.translation!r} model={r.model} similarity={r.similarity}")


def test_madlad():
    from glyphbridge.backends import MadladBackend
    b = MadladBackend()
    t0 = time.time()
    out = b.translate(["Gallia est omnis divisa in partes tres.", "Bugün hava çok güzel."], "la", "en")
    secs = time.time() - t0
    check("madlad la->en", bool(out[0][0].strip()), f"{out[0][0]!r} p={out[0][1]} ({secs:.0f}s incl. load)")
    out = b.translate(["Bugün hava çok güzel."], "tr", "de")
    check("madlad tr->de", bool(out[0][0].strip()), f"{out[0][0]!r} p={out[0][1]}")
    try:
        import psutil
        rss = psutil.Process().memory_info().rss / 1e9
        print(f"INFO process RAM after MADLAD: {rss:.1f} GB", flush=True)
    except ImportError:
        pass


def test_speech():
    import subprocess
    from glyphbridge.speech import speak, transcribe, translate_audio
    d = tempfile.mkdtemp()
    wav = os.path.join(d, "talk.wav")
    speak("Bugün hava çok güzel. Parka gidelim.", "tr", wav)
    flac = os.path.join(d, "talk.flac")  # also exercise ffmpeg decoding of a compressed file
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, flac], check=True)
    heard = transcribe(flac, "tr")
    check("whisper transcribes Turkish speech", "hava" in heard.lower(), repr(heard))
    out, results = translate_audio(flac, target="en", source="tr", speak_out=os.path.join(d, "talk.en.wav"))
    text = open(out, encoding="utf-8").read()
    check("speech -> en translation", "weather" in text.lower(), repr(text))
    check("speech -> en audio written", os.path.getsize(os.path.join(d, "talk.en.wav")) > 1000)


TESTS = {"lid": test_lid, "checker": test_checker, "ocr": test_ocr, "pipeline": test_pipeline, "madlad": test_madlad, "speech": test_speech}

if __name__ == "__main__":
    for name in sys.argv[1:] or list(TESTS):
        try:
            TESTS[name]()
        except Exception as exc:  # report and continue with the next card
            check(name, False, f"{type(exc).__name__}: {exc}")
    sys.exit(1 if check.failed else 0)
