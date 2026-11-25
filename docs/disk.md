# How much disk does Glyphbridge need?

Card sizes are the files `glyphbridge cards install <card>` downloads at the pinned
revision, measured from the Hugging Face file list (25 Nov 2026), not estimates. They land
in the Hugging Face cache (`~/.cache/huggingface`, or `HF_HOME`). Opus-MT pairs are not
pinned and vary by pair (about 0.3 GB each).

| Card | Download / disk | Used for |
|---|---|---|
| `hymt2-q4` | 1.13 GB | 36 languages, best measured for several pairs |
| `gemma-q4` | 2.49 GB | ~55 languages, Latin, low-resource pairs |
| `madlad-int8` | 2.98 GB | 400+ languages (rare languages) |
| `opus:<src>-<tgt>` | ~0.3 GB per pair | one language pair, fast |
| `lid` | 0.78 GB | language detection (1,600+ languages) |
| `checker` | 1.90 GB | meaning checker |
| `emotion` | 0.55 GB | tone check |
| `whisper` | 0.97 GB | speech to text |
| `ota-ocr` | 1.73 GB | Ottoman Turkish OCR (experimental) |
| `madlad` (full) | 11.8 GB | rare languages, full precision |
| `gemma` (full) | 8.64 GB | TranslateGemma full size, images |

Python packages come on top: the `[8gb]` profile needs no PyTorch; the `[transformers]`
profile adds about 0.7 GB on disk (PyTorch 559 MB + Transformers 120 MB, measured on
Windows).

## Typical sets

| Set | Cards | Models on disk | Plus packages | Plan for |
|---|---|---|---|---|
| Smallest useful (one pair) | `opus:tr-en`, `opus:en-tr` | ~0.6 GB | ~0.7 GB | **2 GB** |
| 8 GB profile, light | `hymt2-q4`, `madlad-int8` | 4.1 GB | small | **5 GB** |
| 8 GB profile, all three | `hymt2-q4`, `gemma-q4`, `madlad-int8` | 6.6 GB | small | **8 GB** |
| 8 GB profile + checks | the three above + `lid`, `checker` | 9.3 GB | ~0.7 GB | **11 GB** |
| Everything except full-size | all cards except `madlad`, `gemma` | 12.5 GB | ~1 GB | **15 GB** |
| Everything | all cards | 33.0 GB | ~1 GB | **36 GB** |

"Plan for" adds about 1 GB of headroom. Low-RAM mode (`GLYPHBRIDGE_LOW_RAM=1`) also
writes offloaded layers to `~/.cache/glyphbridge/offload`: plan for up to the size of the
model it runs.

Free space later with `glyphbridge cards remove <card>`.

> Before 25 Nov 2026, `cards install` also downloaded weight formats the code never
> loads (TensorFlow, Flax, ONNX, old versions): `lid` 6.6 GB, `checker` 9.4 GB, `whisper`
> 3.9 GB, `madlad` 15.7 GB, `emotion` 1.6 GB. If you installed those cards earlier,
> `glyphbridge cards remove <card>` and install again to reclaim the space.
