"""Make the GGUF cards run on older CPUs without the user doing anything.

The prebuilt llama-cpp-python wheel for Windows is compiled for newer CPUs; on e.g. a 2015
Core i5 it stops with Windows error 0xc000001d (illegal instruction) and the GGUF cards
(hymt2-q4, gemma-q4, madlad-q4) cannot run. The official llama.cpp Windows CPU release of
the *same build* carries one CPU library per instruction set and picks the one the CPU runs.

``fix()`` (called by ``glyphbridge cards install`` for a GGUF card) runs a one-token test of
the card in a separate process. Only if that crashes with an illegal instruction, it
downloads that release from github.com/ggml-org/llama.cpp (the official project), keeps only
its DLL files in ``~/.cache/glyphbridge/llama-cpu/<build>/`` and tests again with them.
``backends._import_llama`` then uses that folder automatically. ``GLYPHBRIDGE_LLAMA_LIB``
still overrides it; ``GLYPHBRIDGE_LLAMA_AUTOFIX=0`` turns the download off.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from typing import Optional

# llama-cpp-python version -> llama.cpp release built from the same source (the DLL ABI
# must match exactly). Add a line when the pinned llama-cpp-python changes.
BUILDS = {"0.3.38": "b12651"}
RELEASE_URL = "https://github.com/ggml-org/llama.cpp/releases/download/{b}/llama-{b}-bin-win-cpu-x64.zip"
ILLEGAL_INSTRUCTION = 0xC000001D
last_error: list = []


def _version() -> Optional[str]:
    try:
        from importlib.metadata import version
        return version("llama_cpp_python")
    except Exception:  # noqa: BLE001 - not installed
        return None


def build() -> Optional[str]:
    v = _version()
    return BUILDS.get(v) if v else None


def folder(b: Optional[str] = None) -> Optional[str]:
    b = b or build()
    if not b:
        return None
    return os.path.join(os.path.expanduser("~"), ".cache", "glyphbridge", "llama-cpu", b)


def cached_lib() -> Optional[str]:
    """The downloaded release folder for the installed llama-cpp-python, if there is one."""
    if sys.platform != "win32":
        return None
    d = folder()
    return d if d and os.path.isfile(os.path.join(d, "ggml.dll")) else None


_PROBE = r"""
import os, sys
os.environ.pop("GLYPHBRIDGE_LLAMA_AUTOFIX", None)
from glyphbridge.backends import _import_llama
Llama = _import_llama()
m = Llama(model_path=sys.argv[1], n_ctx=64, n_threads=1, verbose=False)
m.eval(m.tokenize(b"Hello")[:2])
print("ok")
"""


def probe(model_path: str, lib: Optional[str] = None, timeout: int = 300) -> int:
    """Return code of a one-token test of ``model_path`` in a fresh process (0 = it runs)."""
    env = dict(os.environ)
    env.pop("LLAMA_CPP_LIB_PATH", None)
    if lib:
        env["GLYPHBRIDGE_LLAMA_LIB"] = lib
    else:
        env.pop("GLYPHBRIDGE_LLAMA_LIB", None)
        env["GLYPHBRIDGE_LLAMA_NO_CACHED_LIB"] = "1"
    try:
        r = subprocess.run([sys.executable, "-c", _PROBE, model_path], env=env, timeout=timeout,
                           capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        return -1
    global last_error
    last_error = (r.stderr or "").strip().splitlines()[-1:]
    return r.returncode & 0xFFFFFFFF


def download(b: str) -> str:
    """Download the official release ``b`` and keep only its DLLs. Returns the folder."""
    import urllib.request
    dest = folder(b)
    os.makedirs(dest, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        z = os.path.join(tmp, "llama.zip")
        urllib.request.urlretrieve(RELEASE_URL.format(b=b), z)
        with zipfile.ZipFile(z) as zf:
            for info in zf.infolist():
                name = os.path.basename(info.filename)
                # Top-level DLLs only: no folders, no "../" paths, no programs.
                if name.lower().endswith(".dll") and name == info.filename and "\\" not in name:
                    with zf.open(info) as src, open(os.path.join(dest, name), "wb") as out:
                        out.write(src.read())
    if not os.path.isfile(os.path.join(dest, "ggml.dll")):
        raise RuntimeError(f"the llama.cpp release {b} has no ggml.dll")
    return dest


def fix(model_path: str, say=print) -> bool:
    """Make sure ``model_path`` (a GGUF card) runs on this CPU. True when it does."""
    if os.environ.get("GLYPHBRIDGE_LLAMA_LIB"):
        return probe(model_path, os.environ["GLYPHBRIDGE_LLAMA_LIB"]) == 0
    code = probe(model_path)
    if code == 0:
        return True
    # The crash reaches Python as OSError "Windows Error 0xc000001d" (exit 1) or kills the process.
    illegal = code == ILLEGAL_INSTRUCTION or any("0xc000001d" in e.lower() for e in last_error)
    have = cached_lib()
    if have and probe(model_path, have) == 0:
        return True
    if not illegal or sys.platform != "win32":
        say(f"  the GGUF card did not start ({(last_error or ['exit code %#x' % code])[0]}); "
            "other cards still translate")
        return False
    b = build()
    if not b or os.environ.get("GLYPHBRIDGE_LLAMA_AUTOFIX") == "0":
        say("  this CPU cannot run the prebuilt llama.cpp; see README 'Older CPUs'")
        return False
    say(f"  this CPU needs another llama.cpp build: downloading the official release {b} (about 30 MB) ...")
    lib = download(b)
    if probe(model_path, lib) == 0:
        say(f"  fixed: GGUF cards now use {lib}")
        return True
    say("  the official release did not run either; see README 'Older CPUs'")
    return False
