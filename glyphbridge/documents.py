"""Document and image translation (v0.2 preview).

* ``.txt`` / ``.md``  - translated line by line, blank lines kept.
* ``.docx``           - every paragraph and table cell is translated in place, so
                        headings, lists, tables and paragraph styles survive.
                        Inline formatting inside a paragraph (one bold word, say)
                        is merged into the paragraph's first run.
* ``.pdf``            - the text layer is extracted page by page and written out as
                        translated text (``.txt``). Layout is not kept yet.
* images              - text is read with Tesseract OCR, then translated.
"""

from __future__ import annotations

import os
from typing import Callable, List, Optional, Sequence

from .engine import TranslationResult, get_engine

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


def ocr_image(path: str, source: str = "auto") -> str:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Image support needs: pip install 'glyphbridge[ocr]' and the Tesseract program") from exc
    if source in (None, "", "auto"):
        langs = "+".join(sorted(set(TESSERACT_LANGS.values()) & set(pytesseract.get_languages(config=""))))
    else:
        langs = TESSERACT_LANGS.get(source, source)
    return pytesseract.image_to_string(Image.open(path), lang=langs or "eng")


def translate_image(path: str, target: str, source: str = "auto", out: Optional[str] = None,
                    translator: Translator = _default_translator):
    text = ocr_image(path, source)
    translated, results = _translate_lines(text.split("\n"), target, source, translator)
    out = out or output_path(path, target, ".txt")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(translated))
    return out, results


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
