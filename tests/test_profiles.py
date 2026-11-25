import pytest

from glyphbridge.profiles import PROFILES, apply_profile


def test_profiles_exist():
    assert set(PROFILES) == {"fast", "balanced", "quality", "low-ram"}


def test_profile_fills_only_unset_settings():
    env = {"GLYPHBRIDGE_EMOTION": "1"}
    applied = apply_profile("fast", env)
    assert env["GLYPHBRIDGE_EMOTION"] == "1"  # the user's own setting wins
    assert "GLYPHBRIDGE_EMOTION" not in applied
    assert env["GLYPHBRIDGE_DISABLE_CHECKER"] == "1"


def test_profile_from_env_and_default():
    env = {"GLYPHBRIDGE_PROFILE": "low-ram"}
    apply_profile(env=env)
    assert env["GLYPHBRIDGE_LOW_RAM"] == "1" and env["GLYPHBRIDGE_MAX_MODELS"] == "1"
    assert apply_profile(env={}) == {}  # balanced = the defaults


def test_unknown_profile():
    with pytest.raises(ValueError):
        apply_profile("turbo", {})


def test_profile_settings_are_real_settings():
    import pathlib
    import re
    src = " ".join(p.read_text(encoding="utf-8") for p in pathlib.Path(__file__).resolve().parents[1]
                   .joinpath("glyphbridge").glob("*.py") if p.name != "profiles.py")
    used = set(re.findall(r"GLYPHBRIDGE_[A-Z_]+", src))
    for settings in PROFILES.values():
        assert set(settings) <= used, set(settings) - used
