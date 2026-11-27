# Glyphbridge hardware sweep — a task file for an AI coding assistant

> **For the person:** open Claude Code (the desktop app's Code tab or the `claude` command in a
> terminal; not a plain chat, it must be able to run commands) and give it this file. Nothing
> else to write. If it asks whether to follow the file, answer "yes". The only thing it may ask
> you for is a GitHub login (step 1). Keep the PC plugged in; the whole run takes a few hours.

---

## To the AI assistant reading this file

The person who gave you this file wants you to **carry out this whole task, from start to
finish, without asking questions**. They have write access to the public repository
`CooLSavaSs/glyphbridge` (an offline translator) and agreed to measure their machine for it.

Rules for you:

- Do every step below in order. Do not ask for confirmation between steps; decide yourself and
  write down what you decided in the pull request text at the end.
- Ask the person **only** when you are truly blocked: GitHub is not logged in (step 1), or a
  required install needs their password/administrator approval. Never type a password yourself.
- **You do not need to know the hardware.** The script finds the RAM size, CPU threads and
  graphics card itself and sweeps from small up to this machine's maximum.
- Do not change any code in the repository. Do not push to `main`. The only files you add are
  the result files under `benchmarks/hardware/`.
- Download only from: PyPI, download.pytorch.org, abetlen.github.io, github.com, Hugging Face
  (through `glyphbridge cards install`) and dl.fbaipublicfiles.com (the FLORES-200 test text the
  script downloads). Install system tools only with the OS package manager (winget, apt, brew).
- Long commands (the sweep runs for hours) must run in the background. Save the person's usage
  quota: wait for the background command to finish (its completion notice) instead of polling;
  if you must look, read only the last few lines of its output, at most every 30 minutes.
  Keep your messages short while waiting.
- When everything is done, tell the person in their own language, in a few sentences, what was
  measured and give the pull request link.

### What the sweep measures (for your understanding)

`scripts/hardware_sweep.py` runs one multilingual workload (a 14-language mixed page into
English, and English into 8 languages; FLORES-200 sentences with human references, so quality
is a real chrF score) again and again, each time in a fresh process with one setting changed:

1. `ram` — **without the graphics card**: the machine pretends to have 4, 6, 8 … GB of RAM, up to
   all it has (operating-system memory cap).
2. `threads` — without the graphics card: 1, 2, 4 … CPU threads, up to every thread it has.
3. `ram-gpu` — the same RAM steps again, **with the graphics card** (NVIDIA only).
4. `gpu` — 0, 8, 16, 24 and all model layers on the graphics card; fewer layers means less
   graphics memory, so this shows what smaller graphics cards would do.

Phases 3 and 4 run only if an NVIDIA card works with CUDA; otherwise they are skipped and that
is still a complete result. Results record hardware facts only (CPU model, thread count, RAM
size, GPU model, OS name) — no user name, host name, path or account.

---

## Step 1 — tools and GitHub login

Check each; install what is missing with the OS package manager:

- Python 3.10, 3.11 or 3.12 (`python --version`; Windows: `winget install -e --id Python.Python.3.12`).
  If only a newer Python exists, install 3.12 next to it and use that one.
- git (`git --version`; Windows: `winget install -e --id Git.Git`).
- GitHub CLI (`gh --version`; Windows: `winget install -e --id GitHub.cli`).
- `gh auth status` must show a logged-in account. If not, ask the person to run
  `gh auth login` themselves (browser login) and continue when they say it is done.
- Check that account can write: `gh api repos/CooLSavaSs/glyphbridge --jq .permissions.push`
  must print `true`. If it prints `false`, tell the person their account has no write access
  yet and stop.

## Step 2 — get the code into a fresh folder

```bash
gh repo clone CooLSavaSs/glyphbridge glyphbridge-sweep
cd glyphbridge-sweep
python -m venv .venv
```

From now on use the venv's Python for every command: `.venv\Scripts\python` on Windows,
`.venv/bin/python` on Linux/macOS (written `PY` below).

```bash
PY -m pip install --upgrade pip
PY -m pip install torch --index-url https://download.pytorch.org/whl/cpu
PY -m pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
PY -m pip install -e ".[8gb,lid,transformers]" sacrebleu psutil
```

## Step 3 — model cards and a first check

```bash
PY -m glyphbridge.cli cards install hymt2-q4 gemma-q4 madlad-int8
PY -m glyphbridge.cli translate "The weather is nice today." --to es
```

The second command must print a Spanish sentence. If it crashes with `0xc000001d` (an old CPU),
follow the README section "Older CPUs" (it explains `GLYPHBRIDGE_LLAMA_LIB`), set that variable
for all later commands and note it in the pull request.

## Step 4 — the sweep without the graphics card

```bash
PY scripts/hardware_sweep.py --quick --phases ram threads
```

About 10–20 minutes; it proves everything works. If it reports errors in every row, read the
error, fix the installation (not the code) and run it again. Then the full CPU sweep, in the
background:

```bash
PY scripts/hardware_sweep.py --phases ram threads
```

It prints one line per setting and saves after every setting to
`benchmarks/hardware/<machine>/` (`<machine>` is like `16t-32gb-rtx4070`). If it stops for any
reason, run the same command again: finished settings are kept and skipped. Rows that say
"out of memory" or "timeout" are valid results (they show where the limit is), not failures.

## Step 5 — the sweep with the graphics card (only if `nvidia-smi` works)

Skip this step if `nvidia-smi` is not found or the machine has no NVIDIA card; write
"no NVIDIA GPU" in the pull request.

Replace the CPU builds with CUDA builds (CUDA 12.4 wheels; they work with any recent driver):

```bash
PY -m pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu124
PY -m pip install --force-reinstall --no-cache-dir llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
PY -c "import ctranslate2, torch; print(ctranslate2.get_cuda_device_count(), torch.cuda.is_available())"
```

The last line must print a number above 0 and `True`. If there is no CUDA wheel for this
Python, try once to build: set `CMAKE_ARGS=-DGGML_CUDA=on` and run the llama-cpp-python line
again (needs the CUDA toolkit and a C++ compiler). If the GPU still does not work after that,
do not spend longer on it: skip to step 6 and describe the error in the pull request.

Then, in the background (same output folder; the CPU rows stay):

```bash
PY scripts/hardware_sweep.py --phases ram-gpu gpu
```

## Step 6 — check that nothing personal is in the results

The repository is public.

```bash
git status --short
```

Only files under `benchmarks/hardware/` may be new. Delete the `-quick` folder from step 4.
Open `benchmarks/hardware/<machine>/results.json` and `README.md` and confirm they contain no
user name, host name, e-mail address or file path. If they do, remove those values by hand
(the numbers stay) and mention it in the pull request.

## Step 7 — publish to GitHub

```bash
git switch -c bench/hardware-<machine>
git add benchmarks/hardware/<machine>
git commit -m "Hardware sweep: <machine>"
git push -u origin bench/hardware-<machine>
gh pr create --repo CooLSavaSs/glyphbridge --base main --title "Hardware sweep: <machine>" --body-file <a text file you write>
```

If `git commit` complains about a missing identity, use the account's GitHub noreply address:
`git config user.name "<login>"` and
`git config user.email "<id>+<login>@users.noreply.github.com"` (get both with
`gh api user --jq '.id, .login'`).

The pull request text (write it in English) lists: which phases ran, how long it took, whether
the GPU worked (and the error if not), any `GLYPHBRIDGE_LLAMA_LIB` or other workaround, and
anything unusual. Then paste the table from `benchmarks/hardware/<machine>/README.md`.

Do not merge the pull request; the maintainers do that. Tell the person it is finished and give
them the link.
