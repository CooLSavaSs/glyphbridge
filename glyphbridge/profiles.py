"""Speed profiles: one switch for the trade-off between speed, RAM and quality.

    glyphbridge translate --profile fast "..." --to en
    GLYPHBRIDGE_PROFILE=low-ram glyphbridge serve

A profile only fills in settings you have not set yourself: an explicit environment
variable always wins. The numbers for each profile (latency, peak RAM, chrF) come from
``scripts/profiles_bench.py``; until it has run in CI they are NOT measured.
"""

from __future__ import annotations

import os
from typing import Dict

PROFILES: Dict[str, Dict[str, str]] = {
    # Smallest cards only, no extra checking model: the quickest answer.
    "fast": {
        "GLYPHBRIDGE_BACKENDS": "opus,madlad-int8",
        "GLYPHBRIDGE_DISABLE_CHECKER": "1",
        "GLYPHBRIDGE_EMOTION": "0",
    },
    # Today's default: measured route table, meaning checker when installed.
    "balanced": {},
    # The large opt-in cards first wherever they are installed.
    "quality": {
        "GLYPHBRIDGE_PREFER": "quality",
    },
    # For PCs with little free RAM: one model at a time, big models streamed from disk,
    # and no ~1 GB checker model next to the translator.
    "low-ram": {
        "GLYPHBRIDGE_LOW_RAM": "1",
        "GLYPHBRIDGE_MAX_MODELS": "1",
        "GLYPHBRIDGE_DISABLE_CHECKER": "1",
        "GLYPHBRIDGE_EMOTION": "0",
    },
}


def apply(name: str, environ=None) -> Dict[str, str]:
    """Set the profile's settings that are not set yet; returns what was set."""
    env = os.environ if environ is None else environ
    if name not in PROFILES:
        raise ValueError(f"Unknown profile {name!r}. Choose one of: {', '.join(PROFILES)}")
    applied = {}
    for key, value in PROFILES[name].items():
        if key not in env:
            env[key] = value
            applied[key] = value
    return applied


def apply_from_env(environ=None) -> Dict[str, str]:
    env = os.environ if environ is None else environ
    name = env.get("GLYPHBRIDGE_PROFILE")
    return apply(name, env) if name else {}


def apply_profile(name=None, env=None) -> Dict[str, str]:
    """``apply(name)``, or with no name the profile in GLYPHBRIDGE_PROFILE (none = balanced)."""
    env = os.environ if env is None else env
    return apply(name, env) if name else apply_from_env(env)
