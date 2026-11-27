"""Hardware sweep: how Glyphbridge behaves on smaller and larger machines.

    python scripts/hardware_sweep.py                 # everything this machine can measure
    python scripts/hardware_sweep.py --quick         # a short check (1 sentence per language)
    python scripts/hardware_sweep.py --phases ram    # only the RAM sweep

One run measures three things on one machine, each setting in its own fresh Python process:

  ram      the machine pretends to be a PC with 4, 6, 8 ... GB of RAM (up to what it has).
           The cap is enforced by the operating system where possible (Linux: a cgroup via
           systemd-run; Windows: a hard working-set limit) at that size minus --os-reserve-gb (what the OS and
           other programs of such a PC use), and Glyphbridge's own RAM budget is set to the same.
           Every row says how the cap was enforced ("cap" column) - "budget" means only
           Glyphbridge's own budget, which simulates its decisions but not swapping.
  threads  1, 2, 4 ... CPU threads, up to every logical core, with no RAM cap.
  ram-gpu  the same RAM steps again, now with the cards on the GPU (NVIDIA + CUDA build only).
  gpu      only with an NVIDIA GPU and a CUDA build: 0, 8, 16, 24 and all model layers on the
           GPU. Fewer layers = less GPU memory, so the measured peak VRAM of each row shows what
           a smaller graphics card would do. (CTranslate2 cards run fully on the GPU or not.)

The workload is the same everywhere and not tied to one language:
  mixed page  14 languages (en de fr es ru uk ar fa zh ja ko hi sw az), language detected
              automatically, everything into English
  one-to-many English into es, ar, zh, hi, sw, tr, fr, ru
Text and human references come from FLORES-200 devtest (CC BY-SA 4.0), so quality is a real
chrF score, not a guess.

Results go to benchmarks/hardware/<machine>/results.json (+ README.md table). <machine> is
built from the hardware only (cores, RAM, GPU); no user name, host name or path is recorded.
A run that stops can be started again: settings already measured are skipped.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

MIXED = [("eng_Latn", "en"), ("deu_Latn", "de"), ("fra_Latn", "fr"), ("spa_Latn", "es"),
         ("rus_Cyrl", "ru"), ("ukr_Cyrl", "uk"), ("arb_Arab", "ar"), ("pes_Arab", "fa"),
         ("zho_Hans", "zh"), ("jpn_Jpan", "ja"), ("kor_Hang", "ko"), ("hin_Deva", "hi"),
         ("swh_Latn", "sw"), ("azj_Latn", "az")]
ONE_TO_MANY = [("spa_Latn", "es"), ("arb_Arab", "ar"), ("zho_Hans", "zh"), ("hin_Deva", "hi"),
               ("swh_Latn", "sw"), ("tur_Latn", "tr"), ("fra_Latn", "fr"), ("rus_Cyrl", "ru")]
GPU_LAYERS = [0, 8, 16, 24, -1]
PHASES = ["ram", "threads", "ram-gpu", "gpu"]   # CPU only first, then the same RAM steps with the GPU


# -- machine description (hardware only) -------------------------------------------
def _nvidia():
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        out = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    gpus = []
    for line in out.strip().splitlines():
        name, mem = [x.strip() for x in line.rsplit(",", 1)]
        gpus.append({"name": name, "vram_mb": int(float(mem))})
    return gpus


def _cpu_name():
    try:
        if sys.platform == "win32":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        if sys.platform == "darwin":
            return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                  capture_output=True, text=True).stdout.strip()
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:  # noqa: BLE001
        pass
    return platform.processor() or "unknown"


def machine():
    import psutil
    ram_gb = round(psutil.virtual_memory().total / 2**30)
    gpus = _nvidia()
    info = {"cpu": _cpu_name(), "cores_physical": psutil.cpu_count(logical=False),
            "cores_logical": psutil.cpu_count(), "ram_gb": ram_gb, "gpus": gpus,
            "os": f"{platform.system()} {platform.release()}", "python": platform.python_version()}
    gpu = re.sub(r"[^a-z0-9]+", "", gpus[0]["name"].lower().replace("nvidia", "").replace("geforce", "")) if gpus else "nogpu"
    info["id"] = f"{info['cores_logical']}t-{ram_gb}gb-{gpu}"
    return info


def commit():
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True).stdout.strip() or None
    except OSError:
        return None


# -- the workload ---------------------------------------------------------------------
def workload(per_lang: int):
    from flores import archive, read
    n = 200 + per_lang * len(MIXED)
    with tarfile.open(archive(), "r:gz") as tar:
        cache = {}

        def lines(code):
            if code not in cache:
                cache[code] = read(tar, code, n)
            return cache[code]
        rows = []
        for i, (fcode, code) in enumerate(MIXED):
            if code == "en":
                continue
            for k in range(per_lang):
                idx = 100 + i * per_lang + k
                rows.append({"set": "mixed", "src": "auto", "lang": code, "tgt": "en",
                             "text": lines(fcode)[idx], "ref": lines("eng_Latn")[idx]})
        for j, (fcode, code) in enumerate(ONE_TO_MANY):
            for k in range(per_lang):
                idx = 150 + j * per_lang + k
                rows.append({"set": "one-to-many", "src": "en", "lang": code, "tgt": code,
                             "text": lines("eng_Latn")[idx], "ref": lines(fcode)[idx]})
    return rows


# -- RAM cap ----------------------------------------------------------------------------
def _windows_ws_cap(limit_mb: int) -> str:
    """Hard-limit the physical RAM (working set) this process may hold. Like a real PC with
    little RAM, the process can still use more memory, but the rest is paged to disk (slow),
    instead of failing. Needs no administrator rights."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.SetProcessWorkingSetSizeEx.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_uint32]
    QUOTA_LIMITS_HARDWS_MIN_DISABLE, QUOTA_LIMITS_HARDWS_MAX_ENABLE = 0x2, 0x4
    ok = k32.SetProcessWorkingSetSizeEx(k32.GetCurrentProcess(), 16 * 2**20, limit_mb * 2**20,
                                        QUOTA_LIMITS_HARDWS_MIN_DISABLE | QUOTA_LIMITS_HARDWS_MAX_ENABLE)
    return "workingset" if ok else "budget"


def _linux_cap_prefix(limit_mb: int):
    """A command prefix that runs the child in a cgroup with MemoryMax, or None."""
    exe = shutil.which("systemd-run")
    if not exe:
        return None, "budget"
    for prefix, label in (([exe, "--user", "--scope", "-q"], "cgroup"),
                          (["sudo", "-n", exe, "--scope", "-q"], "cgroup-sudo")):
        test = subprocess.run(prefix + ["-p", "MemoryMax=64M", "true"], capture_output=True)
        if test.returncode == 0:
            uid = ["--uid", str(os.getuid()), "--gid", str(os.getgid())] if label == "cgroup-sudo" else []
            env = ["-E", "PATH", "-E", "HOME"] if label == "cgroup-sudo" else []
            return prefix + uid + env + ["-p", f"MemoryMax={limit_mb}M"], label
    return None, "budget"


# -- one setting, inside its own process ---------------------------------------------------
class Watch(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop, self.rss, self.vram = threading.Event(), 0, 0
        self.smi = shutil.which("nvidia-smi")

    def run(self):
        import psutil
        proc, tick = psutil.Process(), 0
        while not self.stop.is_set():
            try:
                rss = proc.memory_info().rss + sum(c.memory_info().rss for c in proc.children(recursive=True))
                self.rss = max(self.rss, rss)
                if self.smi and tick % 10 == 0:
                    out = subprocess.run([self.smi, "--query-compute-apps=pid,used_memory",
                                          "--format=csv,noheader,nounits"], capture_output=True, text=True,
                                         timeout=5).stdout
                    used = sum(int(m) for p, m in (l.split(",") for l in out.strip().splitlines() if "," in l)
                               if int(p) == proc.pid)
                    self.vram = max(self.vram, used)
            except Exception:  # noqa: BLE001
                pass
            tick += 1
            self.stop.wait(0.1)


def child(cfg: dict, rows: list) -> dict:
    cap = "none"
    if cfg.get("ram_gb") and sys.platform == "win32":
        cap = _windows_ws_cap(cfg["budget_mb"])
    elif cfg.get("ram_gb"):
        cap = cfg.get("cap", "budget")
    threads = cfg.get("threads")
    if threads:
        try:
            import torch  # type: ignore
            torch.set_num_threads(threads)
        except ImportError:
            pass
    import psutil
    vm = psutil.virtual_memory()
    others_gb = round((vm.total - vm.available - psutil.Process().memory_info().rss) / 2**30, 1)
    watch = Watch()
    watch.start()
    t0 = time.perf_counter()
    from glyphbridge.backends import CACHE
    from glyphbridge.engine import Engine
    engine = Engine()
    first, times = None, []
    for row in rows:
        t = time.perf_counter()
        try:
            r = engine.translate(row["text"], target=row["tgt"], source=row["src"])
            row.update(hyp=r.translation, detected=r.source, card=r.model)
        except Exception as exc:  # noqa: BLE001 - a row that fails is recorded, the run goes on
            row.update(hyp="", detected=None, card=None, error=str(exc)[:200])
        dt = time.perf_counter() - t
        if first is None:
            first = dt
        else:
            times.append(dt)
    total = time.perf_counter() - t0
    watch.stop.set()
    watch.join()

    import sacrebleu

    def chrf(rs):
        return round(sacrebleu.corpus_chrf([r["hyp"] for r in rs], [[r["ref"] for r in rs]]).score, 1) if rs else None
    mixed = [r for r in rows if r["set"] == "mixed"]
    many = [r for r in rows if r["set"] == "one-to-many"]
    per_lang = {}
    for r in rows:
        per_lang.setdefault(f"{r['set']}:{r['lang']}", []).append(r)
    return {**{k: v for k, v in cfg.items() if k != "cap"}, "cap": cap,
            "ram_used_by_other_programs_gb": others_gb,
            "sentences": len(rows), "errors": sum("error" in r for r in rows),
            "first_s": round(first or 0, 1),
            "per_sentence_s": round(sum(times) / len(times), 2) if times else None,
            "total_s": round(total, 1),
            "peak_ram_mb": round(watch.rss / 2**20), "peak_vram_mb": watch.vram or None,
            "chrf_mixed": chrf(mixed), "chrf_one_to_many": chrf(many), "chrf_all": chrf(rows),
            "detected_ok": f"{sum(r['detected'] == r['lang'] for r in mixed)}/{len(mixed)}",
            "cards": sorted({r["card"].split(":")[0] for r in rows if r.get("card")}),
            "refusals": CACHE.refusals,
            "per_lang": {k: {"chrf": chrf(v), "cards": sorted({r["card"].split(":")[0] for r in v if r.get("card")})}
                         for k, v in per_lang.items()},
            "error_sample": next((r["error"] for r in rows if "error" in r), None)}


# -- the sweep -----------------------------------------------------------------------------
def settings(info, phases, ram_list, thread_list, os_reserve_gb):
    out = []
    if "ram" in phases:
        for gb in ram_list:
            out.append({"phase": "ram", "ram_gb": gb, "threads": None, "device": "cpu", "gpu_layers": None,
                        "budget_mb": int(max(1, gb - os_reserve_gb) * 1024)})
    if "threads" in phases:
        for t in thread_list:
            out.append({"phase": "threads", "ram_gb": None, "threads": t, "device": "cpu", "gpu_layers": None})
    if "ram-gpu" in phases and info["gpus"]:
        for gb in ram_list:
            out.append({"phase": "ram-gpu", "ram_gb": gb, "threads": None, "device": "cuda", "gpu_layers": None,
                        "budget_mb": int(max(1, gb - os_reserve_gb) * 1024)})
    if "gpu" in phases and info["gpus"]:
        for n in GPU_LAYERS:
            out.append({"phase": "gpu", "ram_gb": None, "threads": None, "device": "cuda", "gpu_layers": n})
    return out


def key(cfg):
    return f"{cfg['phase']}|{cfg['ram_gb']}|{cfg['threads']}|{cfg['device']}|{cfg['gpu_layers']}"


def run_one(cfg, args, rows_file):
    env = dict(os.environ)
    for k in ("GLYPHBRIDGE_RAM_BUDGET_MB", "GLYPHBRIDGE_THREADS", "GLYPHBRIDGE_DEVICE", "GLYPHBRIDGE_GPU_LAYERS",
              "GLYPHBRIDGE_PROFILE", "OMP_NUM_THREADS"):
        env.pop(k, None)
    env["GLYPHBRIDGE_DEVICE"] = cfg["device"]
    env["PYTHONIOENCODING"] = "utf-8"
    if args.offline:
        env.update(HF_HUB_OFFLINE="1", GLYPHBRIDGE_OFFLINE="1")
    if cfg.get("budget_mb"):
        env["GLYPHBRIDGE_RAM_BUDGET_MB"] = str(cfg["budget_mb"])
    if cfg.get("threads"):
        env["GLYPHBRIDGE_THREADS"] = env["OMP_NUM_THREADS"] = str(cfg["threads"])
    if cfg.get("gpu_layers") is not None:
        env["GLYPHBRIDGE_GPU_LAYERS"] = str(cfg["gpu_layers"])
    cmd = [sys.executable, os.path.abspath(__file__), "--child", json.dumps(cfg), "--rows", rows_file]
    if cfg.get("ram_gb") and sys.platform.startswith("linux"):
        prefix, label = _linux_cap_prefix(cfg["budget_mb"])
        cfg = {**cfg, "cap": label}
        cmd[3] = json.dumps(cfg)
        if prefix:
            cmd = prefix + cmd
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=args.timeout)
    except subprocess.TimeoutExpired:
        return {**cfg, "error": f"timeout after {args.timeout} s"}
    found = [line[7:] for line in proc.stdout.splitlines() if line.startswith("RESULT ")]
    if found:
        return json.loads(found[-1])
    tail = (proc.stderr.strip().splitlines() or [f"exit code {proc.returncode}"])[-1]
    if proc.returncode in (-9, 137, 3221225477, -1073741819) or "MemoryError" in proc.stderr:
        tail = f"out of memory / killed ({tail})"
    return {**cfg, "error": tail[:300]}


def table(rows):
    head = ("| phase | RAM cap | threads | device / GPU layers | cap | load+first s | s / sentence | total s | "
            "peak RAM MB | peak VRAM MB | chrF mixed | chrF 1→many | detected | cards |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    out = []
    for r in rows:
        dev = r["device"] + (f" / {r['gpu_layers']}" if r.get("gpu_layers") is not None else "")
        cells = [r["phase"], f"{r['ram_gb']} GB" if r.get("ram_gb") else "–", r.get("threads") or "all", dev]
        if "error" in r and "sentences" not in r:
            out.append("| " + " | ".join(map(str, cells)) + f" | {r.get('cap', '–')} | error: {r['error'][:60]} |"
                       + " – |" * 8)
            continue
        cells += [r["cap"], r["first_s"], r["per_sentence_s"], r["total_s"], r["peak_ram_mb"],
                  r["peak_vram_mb"] or "–", r["chrf_mixed"], r["chrf_one_to_many"], r["detected_ok"],
                  ", ".join(r["cards"]) + (f" ({r['errors']} errors)" if r["errors"] else "")]
        out.append("| " + " | ".join(map(str, cells)) + " |")
    return head + "\n".join(out)


def write(outdir, info, rows):
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "results.json"), "w", encoding="utf-8") as fh:
        json.dump({"machine": info, "rows": rows}, fh, ensure_ascii=False, indent=1)
    gpus = ", ".join(f"{g['name']} {g['vram_mb'] // 1024} GB" for g in info["gpus"]) or "none"
    md = (f"# Hardware sweep: {info['id']}\n\n"
          f"- CPU: {info['cpu']} ({info['cores_physical']} cores / {info['cores_logical']} threads)\n"
          f"- RAM: {info['ram_gb']} GB · GPU: {gpus} · {info['os']} · Python {info['python']}\n"
          f"- Glyphbridge commit: {info.get('commit')} · {info.get('date')} · "
          f"{info.get('per_lang')} sentence(s) per language, OS reserve {info.get('os_reserve_gb')} GB\n\n"
          "How to read it: `scripts/hardware_sweep.py` (module docstring). chrF is against FLORES-200 "
          "human references; higher is better.\n\n" + table(rows) + "\n")
    with open(os.path.join(outdir, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(md)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phases", nargs="*", default=PHASES, choices=PHASES)
    ap.add_argument("--ram-gb", nargs="*", type=float, help="RAM sizes to pretend (default 4, 6, 8 ... total)")
    ap.add_argument("--threads", nargs="*", type=int, help="thread counts (default 1, 2, 4 ... all)")
    ap.add_argument("--os-reserve-gb", type=float, default=2.0,
                    help="RAM a real PC of that size loses to the OS and other programs (default 2)")
    ap.add_argument("--per-lang", type=int, default=2, help="sentences per language (default 2)")
    ap.add_argument("--quick", action="store_true", help="1 sentence per language, fewer settings")
    ap.add_argument("--timeout", type=int, default=3600, help="seconds per setting before it counts as failed")
    ap.add_argument("--out", help="output folder (default benchmarks/hardware/<machine>)")
    ap.add_argument("--no-warmup", action="store_true", help="skip the unmeasured first pass that downloads models")
    ap.add_argument("--offline", action="store_true", default=True, help=argparse.SUPPRESS)
    ap.add_argument("--child", help=argparse.SUPPRESS)
    ap.add_argument("--rows", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if args.child:
        with open(args.rows, encoding="utf-8") as fh:
            rows = json.load(fh)
        print("RESULT " + json.dumps(child(json.loads(args.child), rows), ensure_ascii=False), flush=True)
        return 0

    if sys.platform == "win32":   # keep the PC awake while the sweep runs (no setting is changed)
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    info = machine()
    per_lang = 1 if args.quick else args.per_lang
    info.update(commit=commit(), date=time.strftime("%Y-%m-%d"), per_lang=per_lang, os_reserve_gb=args.os_reserve_gb)
    total = info["ram_gb"]
    ram_list = args.ram_gb or ([4, 8, min(16, total)] if args.quick else list(range(4, int(total) + 1, 2)))
    ram_list = sorted({g for g in ram_list if g <= total})
    logical = info["cores_logical"] or 2
    thread_list = args.threads or sorted({t for t in [1, 2, 4, 8, 16, 32, 64, 128] if t < logical} | {logical})
    if args.quick and not args.threads:
        thread_list = sorted({1, max(1, logical // 2), logical})
    plan = settings(info, args.phases, ram_list, thread_list, args.os_reserve_gb)
    outdir = args.out or os.path.join(ROOT, "benchmarks", "hardware", info["id"] + ("-quick" if args.quick else ""))

    done = []
    old = os.path.join(outdir, "results.json")
    if os.path.exists(old):
        with open(old, encoding="utf-8") as fh:
            done = [r for r in json.load(fh)["rows"] if "error" not in r or "sentences" in r]
    have = {key(r) for r in done}
    print(f"machine {info['id']}: {info['cpu']}, {total} GB RAM, GPU: {info['gpus'] or 'none'}", flush=True)
    print(f"{len(plan)} settings, {len(have & {key(c) for c in plan})} already measured -> {outdir}", flush=True)
    if {"gpu", "ram-gpu"} & set(args.phases) and not info["gpus"]:
        print("no NVIDIA GPU found (nvidia-smi): the GPU phases are skipped", flush=True)

    import tempfile
    rows_file = os.path.join(tempfile.mkdtemp(prefix="gb-sweep-"), "rows.json")
    with open(rows_file, "w", encoding="utf-8") as fh:
        json.dump(workload(per_lang), fh, ensure_ascii=False)

    if not args.no_warmup:
        print("warm-up (not measured): downloads any model the workload needs ...", flush=True)
        args.offline = False
        warm = run_one({"phase": "warmup", "ram_gb": None, "threads": None, "device": "cpu", "gpu_layers": None},
                       args, rows_file)
        args.offline = True
        print(f"  warm-up: {warm.get('error') or 'ok, cards ' + ', '.join(warm.get('cards', []))}", flush=True)

    rows = list(done)
    for i, cfg in enumerate(plan, 1):
        if key(cfg) in have:
            continue
        print(f"[{i}/{len(plan)}] {key(cfg)} ...", flush=True)
        res = run_one(cfg, args, rows_file)
        rows.append(res)
        print("   " + table([res]).splitlines()[-1], flush=True)
        write(outdir, info, rows)   # after every setting, so a stopped run keeps what it measured
    write(outdir, info, rows)
    print(f"\ndone -> {outdir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
