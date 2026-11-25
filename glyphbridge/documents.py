"""Document and image translation (v0.2 preview).

* ``.txt`` / ``.md``  - translated line by line, blank lines kept.
* ``.docx``           - every paragraph and table cell is translated in place, so
                        headings, lists, tables and paragraph styles survive.
                        Inline formatting inside a paragraph (one bold word, say)
                        is merged into the paragraph's first run.
* ``.pdf``            - the text layer is extracted page by page and written out as
                        translated text (``.txt``). Layout is not kept yet.
* images              - text is read line by line with Tesseract OCR (each result carries
                        the line's ``ocr_confidence``), then translated.
"""

from __future__ import annotations

import os
from typing import Callable, List, Optional, Sequence, Tuple

from .engine import TranslationResult, get_engine, needs_review

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}

# Tesseract language packs use ISO 639-2/3 codes.
TESSERACT_LANGS = {
    "en": "eng", "tr": "tur", "de": "deu", "fr": "fra", "es": "spa", "it": "ita", "pt": "por",
    "ru": "rus", "ar": "ara", "zh": "chi_sim", "ja": "jpn", "ko": "kor", "hi": "hin", "nl": "nld",
    "pl": "pol", "uk": "ukr", "fa": "fas", "el": "ell", "he": "heb", "la": "lat", "az": "aze",
}

Translator = Callable[[Sequence[str], str, str], List[TranslationResult]]


def _default_translator(texts: Sequence[str], target: str, source: str) -> List[TranslationResult]:
    return get_engine().translate_batch(texts, target=target, source=source)


def output_path(path: str, target: str, ext: Optional[str] = None) -> str:
    stem, old_ext = os.path.splitext(path)
    return f"{stem}.{target}{ext or old_ext}"


def _translate_lines(lines: Sequence[str], target: str, source: str, tr: Translator):
    idx = [i for i, line in enumerate(lines) if line.strip()]
    results = tr([lines[i] for i in idx], target, source) if idx else []
    out = list(lines)
    for i, r in zip(idx, results):
        out[i] = r.translation
    return out, results


def translate_text_file(path: str, target: str, source: str = "auto", out: Optional[str] = None,
                        translator: Translator = _default_translator):
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    translated, results = _translate_lines(lines, target, source, translator)
    out = out or output_path(path, target)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(translated))
    return out, results


def _docx_paragraphs(doc) -> list:
    paras = list(doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                paras.extend(cell.paragraphs)
    return paras


def translate_docx(path: str, target: str, source: str = "auto", out: Optional[str] = None,
                   translator: Translator = _default_translator):
    try:
        import docx  # type: ignore
    except ImportError as exc:
        raise RuntimeError("DOCX support needs: pip install 'glyphbridge[docs]'") from exc
    document = docx.Document(path)
    paras = [p for p in _docx_paragraphs(document) if p.text.strip()]
    results = translator([p.text for p in paras], target, source) if paras else []
    for para, res in zip(paras, results):
        runs = para.runs
        if runs:
            runs[0].text = res.translation
            for run in runs[1:]:
                run.text = ""
        else:
            para.add_run(res.translation)
    out = out or output_path(path, target)
    document.save(out)
    return out, results


def translate_pdf(path: str, target: str, source: str = "auto", out: Optional[str] = None,
                  translator: Translator = _default_translator):
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PDF support needs: pip install 'glyphbridge[docs]'") from exc
    pages = [(page.extract_text() or "") for page in PdfReader(path).pages]
    chunks: List[str] = []
    all_results: List[TranslationResult] = []
    for n, text in enumerate(pages, 1):
        translated, results = _translate_lines(text.split("\n"), target, source, translator)
        chunks.append(f"--- page {n} ---\n" + "\n".join(translated))
        all_results.extend(results)
    out = out or output_path(path, target, ".txt")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(chunks))
    return out, all_results


def _tesseract(source: str):
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Image support needs: pip install 'glyphbridge[ocr]' and the Tesseract program") from exc
    if source in (None, "", "auto"):
        langs = "+".join(sorted(set(TESSERACT_LANGS.values()) & set(pytesseract.get_languages(config=""))))
    else:
        langs = TESSERACT_LANGS.get(source, source)
    return pytesseract, Image, langs or "eng"


def ocr_image(path: str, source: str = "auto") -> str:
    pytesseract, Image, langs = _tesseract(source)
    return pytesseract.image_to_string(Image.open(path), lang=langs)


# Below this OCR confidence the photo itself is the problem: tell the user what to do.
RETAKE_BELOW = 0.50
RETAKE_HINT = "low OCR confidence: move closer, hold steady or retake the photo"


def ocr_regions(path: str, source: str = "auto") -> List[dict]:
    """OCR text line by line: ``{"text", "box": (left, top, right, bottom), "ocr_confidence"}``.
    The box is in image pixels, so a viewer can place the translation over the photo;
    the confidence is Tesseract's mean word confidence for the line (0-1)."""
    pytesseract, Image, langs = _tesseract(source)
    data = pytesseract.image_to_data(Image.open(path), lang=langs, output_type=pytesseract.Output.DICT)
    lines: "dict[tuple, list]" = {}
    for i, word in enumerate(data.get("text", [])):
        if not str(word).strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        left, top = int(data.get("left", [0] * (i + 1))[i]), int(data.get("top", [0] * (i + 1))[i])
        right = left + int(data.get("width", [0] * (i + 1))[i])
        bottom = top + int(data.get("height", [0] * (i + 1))[i])
        lines.setdefault(key, []).append((str(word), float(data["conf"][i]), (left, top, right, bottom)))
    out = []
    for key in sorted(lines):
        words = lines[key]
        confs = [c for _, c, _ in words if c >= 0]  # Tesseract uses -1 for "no confidence"
        boxes = [b for _, _, b in words]
        out.append({"text": " ".join(w for w, _, _ in words),
                    "box": (min(b[0] for b in boxes), min(b[1] for b in boxes),
                            max(b[2] for b in boxes), max(b[3] for b in boxes)),
                    "ocr_confidence": round(sum(confs) / len(confs) / 100, 4) if confs else None})
    return out


def ocr_lines(path: str, source: str = "auto") -> List[Tuple[str, Optional[float]]]:
    """OCR text line by line with Tesseract's mean word confidence for each line (0-1)."""
    return [(r["text"], r["ocr_confidence"]) for r in ocr_regions(path, source)]


def translate_image(path: str, target: str, source: str = "auto", out: Optional[str] = None,
                    translator: Translator = _default_translator):
    """Photo mode: each OCR line is translated and keeps its box and OCR confidence; a line
    read with low confidence asks for a closer or new photo. Fix OCR mistakes by editing the
    text from ``--ocr-only`` and translating that file."""
    regions = ocr_regions(path, source)
    translated, results = _translate_lines([g["text"] for g in regions], target, source, translator)
    for r, g in zip(results, regions):  # every OCR line has text, so they pair up 1:1
        r.ocr_confidence = g["ocr_confidence"]
        r.box = tuple(g["box"])
        if r.ocr_confidence is not None and r.ocr_confidence < RETAKE_BELOW:
            r.issues = list(r.issues) + [RETAKE_HINT]
        r.expert_review_required = needs_review(r)
    out = out or output_path(path, target, ".txt")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(translated))
    return out, results


def ocr_only(path: str, source: str = "auto", out: Optional[str] = None) -> Tuple[str, List[dict]]:
    """Write the OCR text (one line per OCR line) for the user to correct, without translating."""
    regions = ocr_regions(path, source)
    out = out or os.path.splitext(path)[0] + ".ocr.txt"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(g["text"] for g in regions))
    return out, regions


def translate_file(path: str, target: str, source: str = "auto", out: Optional[str] = None,
                   translator: Translator = _default_translator):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return translate_docx(path, target, source, out, translator)
    if ext == ".pdf":
        return translate_pdf(path, target, source, out, translator)
    if ext in IMAGE_EXTS:
        return translate_image(path, target, source, out, translator)
    return translate_text_file(path, target, source, out, translator)
