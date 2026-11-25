"""Printed Ottoman Turkish (Arabic script): page image -> lines -> OCR -> editable text.

Status: experimental (v0.4 work in progress). The pipeline is

1. **Lines**: the page is cut into text lines. Built in: a horizontal projection profile,
   which suits clean printed (nesih/matbu) pages. Handwriting (rika, divani) and skewed or
   multi-column pages need a real layout model such as Kraken (planned, optional).
2. **OCR**: each line image goes to the ``ota-ocr`` card (Azra 1-Mini 0.8B, Apache 2.0),
   a vision-language model trained on Ottoman *line* images.
3. **Output**: editable Arabic-script text, one line per OCR line, every line marked for
   expert review. Transliteration to Latin letters and modern Turkish are NOT done yet:
   no openly licensed model with weights was found for them (see the work plan).

Accuracy is not measured by us yet; the model authors report 80.2% character accuracy
on printed nesih and 67.1% on handwritten rika.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

# The prompt the model was trained with (from its model card).
PROMPT = "Görseldeki Osmanlıca metni transkribe et:"

# The model often writes the Arabic code points of letters that Ottoman (like Persian)
# writes with other ones: KAF U+0643 for KEHEH U+06A9, YEH U+064A / ALEF MAKSURA U+0649
# for FARSI YEH U+06CC. They look alike but differ for search, copy and comparison.
# On the model card's 10 sample lines this alone moved character accuracy from 87.0% to
# 96.9% (printed nesih) and 76.4% to 86.5% (handwritten rika).
_OTTOMAN_LETTERS = str.maketrans({"\u0643": "\u06a9", "\u064a": "\u06cc", "\u0649": "\u06cc"})


def normalize_ottoman(text: str) -> str:
    """Ottoman (Persian-style) code points for kaf and ye."""
    return text.translate(_OTTOMAN_LETTERS)
REVIEW_NOTE = ("Machine OCR of a historical script: check every line against the image "
               "before using it. Transliteration and modern Turkish are not available yet.")


@dataclass
class OttomanLine:
    index: int
    box: Tuple[int, int, int, int]   # left, top, right, bottom in page pixels
    text: str
    detected_script: Optional[str] = None
    expert_review_required: bool = True
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# 1. Line segmentation
def _ink_rows(gray, threshold: Optional[int] = None) -> Tuple[List[int], int]:
    """Dark-pixel count per row of a grayscale PIL image, and the threshold used."""
    w, h = gray.size
    try:
        import numpy as np  # type: ignore
        a = np.asarray(gray, dtype="uint8")
        t = int(threshold if threshold is not None else min(200, a.mean() * 0.75))
        return (a < t).sum(axis=1).astype(int).tolist(), t
    except ImportError:
        px = list(gray.getdata())
        t = int(threshold if threshold is not None else min(200, (sum(px) / len(px)) * 0.75))
        return [sum(1 for v in px[y * w:(y + 1) * w] if v < t) for y in range(h)], t


def segment_lines(image, min_height: int = 8, min_gap: int = 3, pad: int = 4,
                  min_ink_fraction: float = 0.004) -> List[Tuple[int, int, int, int]]:
    """Boxes (left, top, right, bottom) of the text lines on a page, top to bottom.

    Rows that hold more than ``min_ink_fraction`` of the page width in dark pixels are
    text; runs of text rows form a line; gaps shorter than ``min_gap`` rows are bridged
    (dots and diacritics above/below Arabic letters often leave thin blank rows)."""
    gray = image.convert("L")
    w, h = gray.size
    rows, threshold = _ink_rows(gray)
    limit = max(1, int(w * min_ink_fraction))
    runs: List[List[int]] = []
    start = None
    blank = 0
    for y, n in enumerate(rows + [0] * (min_gap + 1)):
        if n >= limit:
            if start is None:
                start = y
            blank = 0
            end = y
        elif start is not None:
            blank += 1
            if blank > min_gap:
                runs.append([start, end])
                start, blank = None, 0
    boxes = []
    for top, bottom in runs:
        if bottom - top + 1 < min_height:
            continue  # specks, page noise
        top, bottom = max(0, top - pad), min(h, bottom + 1 + pad)
        band = gray.crop((0, top, w, bottom))
        cols = _ink_rows(band.rotate(90, expand=True), threshold)[0]  # column ink, right-to-left
        cols = cols[::-1]
        inked = [x for x, n in enumerate(cols) if n > 0]
        left, right = (max(0, inked[0] - pad), min(w, inked[-1] + 1 + pad)) if inked else (0, w)
        boxes.append((left, top, right, bottom))
    return boxes


# ---------------------------------------------------------------------------
# 2. Line OCR with the ota-ocr card
class AzraOCR:
    """Azra 1-Mini on CPU through Transformers (no remote code is executed)."""

    def __init__(self, device: str = "cpu", dtype: Optional[str] = None):
        self.device = device
        # bfloat16 halves the RAM; GLYPHBRIDGE_OTA_DTYPE=float32 matches the model card exactly.
        self.dtype = dtype or os.environ.get("GLYPHBRIDGE_OTA_DTYPE", "bfloat16")
        self._loaded = None

    def _load(self):
        if self._loaded is None:
            try:
                import torch  # type: ignore
                from transformers import AutoModelForImageTextToText, AutoProcessor  # type: ignore
            except ImportError as exc:
                raise RuntimeError('ota-ocr needs: pip install "glyphbridge[transformers,ocr]" '
                                   "(transformers>=5.14)") from exc
            from .cards import CARDS, offline
            card = CARDS["ota-ocr"]
            kw = {"revision": card.revision, "local_files_only": offline()}
            processor = AutoProcessor.from_pretrained(card.repo, **kw)
            model = AutoModelForImageTextToText.from_pretrained(
                card.repo, dtype=getattr(torch, self.dtype), low_cpu_mem_usage=True, **kw).to(self.device).eval()
            self._loaded = (processor, model)
        return self._loaded

    @staticmethod
    def prepare(image):
        """RGB, both sides rounded up to a multiple of 64 (as the model card does)."""
        image = image.convert("RGB")
        w, h = image.size
        size = (((w + 63) // 64) * 64, ((h + 63) // 64) * 64)
        if size != (w, h):
            from PIL import Image  # type: ignore
            image = image.resize(size, Image.Resampling.LANCZOS)
        return image

    def read_line(self, image) -> str:
        import torch  # type: ignore
        processor, model = self._load()
        image = self.prepare(image)
        messages = [{"role": "user", "content": [{"type": "image", "image": image},
                                                 {"type": "text", "text": PROMPT}]}]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=[image], padding=True, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            ids = model.generate(**inputs, max_new_tokens=512, do_sample=False, repetition_penalty=1.2,
                                 no_repeat_ngram_size=3, pad_token_id=processor.tokenizer.pad_token_id,
                                 eos_token_id=processor.tokenizer.eos_token_id)
        text = processor.batch_decode(ids[:, inputs.input_ids.shape[1]:], skip_special_tokens=True,
                                      clean_up_tokenization_spaces=False)[0].strip()
        return normalize_ottoman(text)


LineReader = Callable[[object], str]


# ---------------------------------------------------------------------------
# 3. Page -> editable text
def read_page(path_or_image, reader: Optional[LineReader] = None, lines_already: bool = False,
              **segment_kw) -> List[OttomanLine]:
    """OCR a printed Ottoman page (or a single line image with ``lines_already=True``)."""
    from PIL import Image  # type: ignore
    from .engine import detect_script
    image = Image.open(path_or_image) if isinstance(path_or_image, (str, os.PathLike)) else path_or_image
    reader = reader or AzraOCR().read_line
    boxes = [(0, 0, image.width, image.height)] if lines_already else segment_lines(image, **segment_kw)
    out = []
    for i, box in enumerate(boxes):
        text = reader(image.crop(box))
        notes = [] if text.strip() else ["empty OCR output"]
        script = detect_script(text)
        if text.strip() and script != "Arab":
            notes.append(f"OCR output is not in Arabic script ({script})")
        out.append(OttomanLine(i, box, text, script, True, notes))
    return out


def to_text(lines: Sequence[OttomanLine]) -> str:
    return "\n".join(line.text for line in lines)
