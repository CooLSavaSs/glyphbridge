"""Tests that run without downloading any model: backends and checker are faked."""

import json

import pytest
from fastapi.testclient import TestClient

import glyphbridge.engine as engine_mod
from glyphbridge import cli
from glyphbridge.backends import Backend, BackendUnavailable, ModelCache
from glyphbridge.engine import Engine, TranslationError
from glyphbridge.server import create_app


class FakeBackend(Backend):
    def __init__(self, name, table, prob=0.9, broken=False):
        self.name, self.table, self.prob, self.broken = name, table, prob, broken

    def supports(self, s, t):
        return (s, t) in self.table

    def translate(self, texts, s, t):
        if self.broken:
            raise BackendUnavailable("offline")
        return [(self.table[(s, t)].get(x, x.upper()), self.prob) for x in texts]


class FakeChecker:
    """Similarity = 1.0 unless the translation contains 'BAD'."""
    def __init__(self, enabled=True, threshold=0.75):
        self.enabled, self.threshold = enabled, threshold

    def similarity(self, sources, outs):
        if not self.enabled:
            return [None] * len(outs)
        return [0.3 if "BAD" in o else 0.95 for o in outs]

    def passes(self, s):
        return s is None or s >= self.threshold


OPUS = FakeBackend("opus", {
    ("tr", "en"): {"Merhaba dünya": "Hello world", "Nasılsın?": "How are you?", "Zor cümle": "BAD output"},
    ("en", "de"): {"Hello world": "Hallo Welt", "How are you?": "Wie geht es dir?"},
})
MADLAD = FakeBackend("madlad", {
    ("tr", "en"): {"Zor cümle": "Difficult sentence"},
    ("la", "tr"): {"Carpe diem": "Günü yakala"},
}, prob=0.8)


@pytest.fixture
def eng(monkeypatch):
    e = Engine(backends=[OPUS, MADLAD], checker=FakeChecker())
    monkeypatch.setattr(engine_mod, "_default", e)
    return e


def test_direct_translation(eng):
    r = eng.translate("Merhaba dünya", target="en", source="tr")
    assert r.translation == "Hello world" and r.model == "opus:tr-en"
    assert r.confidence == 0.95 and not r.flagged


def test_checker_sends_bad_sentence_to_next_backend(eng):
    r = eng.translate("Zor cümle", target="en", source="tr")
    assert r.translation == "Difficult sentence"
    assert r.model == "madlad:tr-en"
    assert r.attempts == ["opus:tr-en", "madlad:tr-en"]


def test_flagged_when_no_backend_passes(monkeypatch):
    e = Engine(backends=[OPUS], checker=FakeChecker())
    r = e.translate("Zor cümle", target="en", source="tr")
    assert r.flagged and r.translation == "BAD output"


def test_rare_language_goes_to_madlad(eng):
    r = eng.translate("Carpe diem", target="tr", source="la")
    assert r.translation == "Günü yakala" and r.model.startswith("madlad")


def test_pivot_through_english(eng):
    r = eng.translate("Merhaba dünya", target="de", source="tr")
    assert r.translation == "Hallo Welt"
    assert "->" in r.model


def test_without_checker_uses_model_probability():
    e = Engine(backends=[OPUS], checker=FakeChecker(enabled=False))
    r = e.translate("Merhaba dünya", target="en", source="tr")
    assert r.confidence == 0.9 and r.similarity is None


def test_unavailable_backend_is_skipped():
    broken = FakeBackend("gemma", {("tr", "en"): {}}, broken=True)
    e = Engine(backends=[broken, OPUS], checker=FakeChecker())
    assert e.translate("Merhaba dünya", target="en", source="tr").model == "opus:tr-en"


def test_same_language_and_unsupported(eng):
    assert eng.translate("Selam", target="tr", source="tr").translation == "Selam"
    with pytest.raises(TranslationError):
        eng.translate("x", target="ja", source="fr")


def test_auto_detect(eng, monkeypatch):
    monkeypatch.setattr(engine_mod.lid, "detect", lambda text: "tr")
    assert eng.translate("Merhaba dünya", target="en").source == "tr"


def test_model_cache_respects_ram_budget():
    cache = ModelCache(budget_mb=1000, max_models=5)
    cache.get("a", lambda: "A", 600)
    cache.get("b", lambda: "B", 300)
    assert list(cache._items) == ["a", "b"]
    cache.get("c", lambda: "C", 600)          # a must go to make room
    assert list(cache._items) == ["b", "c"] and cache.used_mb == 900
    cache.get("big", lambda: "BIG", 5000)     # alone over budget: allowed, others unloaded
    assert list(cache._items) == ["big"]


def test_cards_cli_lists_cards(monkeypatch, capsys):
    from glyphbridge import cards
    monkeypatch.setattr(cards, "_cached_repos", lambda: {"google/madlad400-3b-mt", "Helsinki-NLP/opus-mt-tc-big-en-tr"})
    monkeypatch.setenv("GLYPHBRIDGE_RAM_BUDGET_MB", "4000")
    assert cli.main(["cards"]) == 0
    out = capsys.readouterr().out
    assert "[\u2713] madlad" in out and "[ ] gemma" in out and "opus:en-tr" in out


def test_card_resolution():
    from glyphbridge import cards
    assert cards.resolve("opus:tr-en").repo == "Helsinki-NLP/opus-mt-tc-big-tr-en"
    with pytest.raises(KeyError):
        cards.resolve("nope")


def test_package_level_translate(eng):
    import glyphbridge
    assert glyphbridge.translate("Merhaba dünya", to="en", source="tr").translation == "Hello world"


def test_api(eng):
    client = TestClient(create_app(engine=eng, api_key=""))
    res = client.post("/v1/translate", json={"text": "Merhaba dünya", "source": "tr", "target": "en"})
    assert res.status_code == 200 and res.json()["translation"] == "Hello world"
    res = client.post("/v1/translate", json={"texts": ["Merhaba dünya", "Nasılsın?"], "source": "tr", "target": "en"})
    assert [r["translation"] for r in res.json()["results"]] == ["Hello world", "How are you?"]


def test_api_key_required(eng):
    client = TestClient(create_app(engine=eng, api_key="s3cret"))
    body = {"text": "Merhaba dünya", "source": "tr", "target": "en"}
    assert client.post("/v1/translate", json=body).status_code == 401
    assert client.post("/v1/translate", json=body, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/v1/translate", json=body, headers={"Authorization": "Bearer s3cret"}).status_code == 200
    assert client.post("/v1/translate", json=body, headers={"X-API-Key": "s3cret"}).status_code == 200
    assert client.get("/v1/health").json()["auth"] is True


def test_api_errors(eng):
    client = TestClient(create_app(engine=eng, api_key=""))
    assert client.post("/v1/translate", json={"target": "en"}).status_code == 422
    assert client.post("/v1/translate", json={"text": "x", "source": "fr", "target": "ja"}).status_code == 400


def test_cli_keeps_paragraphs_and_warns(eng, tmp_path, capsys):
    f = tmp_path / "in.txt"
    f.write_text("Merhaba dünya\n\nNasılsın?", encoding="utf-8")
    assert cli.main(["translate", "--file", str(f), "--from", "tr", "--to", "en"]) == 0
    assert capsys.readouterr().out.strip() == "Hello world\n\nHow are you?"


def test_cli_flags_low_confidence(capsys, monkeypatch):
    e = Engine(backends=[OPUS], checker=FakeChecker())
    monkeypatch.setattr(engine_mod, "_default", e)
    assert cli.main(["translate", "Zor cümle", "--from", "tr", "--to", "en"]) == 0
    assert "⚠" in capsys.readouterr().err


def test_cli_json(eng, capsys):
    assert cli.main(["translate", "Merhaba", "dünya", "--from", "tr", "--to", "en", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["translation"] == "Hello world"


def test_cli_serve_refuses_public_without_key(monkeypatch):
    monkeypatch.delenv("GLYPHBRIDGE_API_KEY", raising=False)
    assert cli.main(["serve", "--host", "0.0.0.0"]) == 2


def test_docx_translation_keeps_structure(eng, tmp_path):
    docx = pytest.importorskip("docx")
    from glyphbridge.documents import translate_file
    src = tmp_path / "in.docx"
    d = docx.Document()
    d.add_heading("Merhaba dünya", level=1)
    d.add_paragraph("")
    table = d.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Nasılsın?"
    d.save(src)
    out, results = translate_file(str(src), target="en", source="tr")
    assert out.endswith("in.en.docx") and len(results) == 2
    back = docx.Document(out)
    assert back.paragraphs[0].text == "Hello world"
    assert back.paragraphs[0].style.name.startswith("Heading")
    assert back.tables[0].cell(0, 0).text == "How are you?"


def test_text_file_with_output(eng, tmp_path, capsys):
    src = tmp_path / "a.txt"
    src.write_text("Merhaba dünya\n\nNasılsın?", encoding="utf-8")
    dst = tmp_path / "b.txt"
    assert cli.main(["translate", "--file", str(src), "--from", "tr", "--to", "en", "-o", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == "Hello world\n\nHow are you?"
    assert "2 segments" in capsys.readouterr().out


def test_image_ocr_path(eng, tmp_path, monkeypatch):
    from glyphbridge import documents
    monkeypatch.setattr(documents, "ocr_image", lambda path, source="auto": "Merhaba dünya\n")
    img = tmp_path / "photo.png"
    img.write_bytes(b"")
    out, results = documents.translate_file(str(img), target="en", source="tr")
    assert out.endswith("photo.en.txt")
    assert open(out, encoding="utf-8").read().startswith("Hello world")


def test_audio_translation(eng, tmp_path, monkeypatch, capsys):
    from glyphbridge import speech
    monkeypatch.setattr(speech, "transcribe", lambda path, source="auto": "Nasılsın? Nasılsın?")
    spoken = {}
    monkeypatch.setattr(speech, "speak", lambda text, lang, out: spoken.update(text=text, lang=lang, out=out) or out)
    audio = tmp_path / "talk.wav"
    audio.write_bytes(b"")
    assert cli.main(["translate", "--file", str(audio), "--from", "tr", "--to", "en", "--speak"]) == 0
    out = (tmp_path / "talk.en.txt").read_text(encoding="utf-8")
    assert "How are you? How are you?" in out and "Nasılsın? Nasılsın?" in out
    assert spoken["lang"] == "en" and spoken["out"].endswith("talk.en.wav")


def test_sentence_split():
    from glyphbridge.speech import _split_sentences
    assert _split_sentences("Bir. İki? Üç") == ["Bir.", " İki?", " Üç"]


def test_listen_translates_each_chunk(eng, monkeypatch):
    from glyphbridge import speech
    heard = {"a.wav": "Merhaba dünya", "b.wav": "", "c.wav": "Nasılsın?"}
    monkeypatch.setattr(speech, "transcribe", lambda path, source="auto": heard[path])
    lines = []
    n = speech.listen(target="en", source="tr", chunks=["a.wav", "b.wav", "c.wav"], emit=lines.append)
    assert n == 2
    assert "Hello world" in lines[0] and "How are you?" in lines[1]


def test_openai_compatible_endpoint(eng):
    client = TestClient(create_app(engine=eng, api_key="k"))
    h = {"Authorization": "Bearer k"}
    models = client.get("/v1/models", headers=h).json()["data"]
    assert {"id": "glyphbridge-en", "object": "model", "owned_by": "glyphbridge"} in models
    body = {"model": "glyphbridge-en", "source": "tr",
            "messages": [{"role": "system", "content": "translate"},
                         {"role": "user", "content": [{"type": "text", "text": "Merhaba dünya"}]}]}
    res = client.post("/v1/chat/completions", json=body, headers=h)
    assert res.status_code == 200
    data = res.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"] == {"role": "assistant", "content": "Hello world"}
    assert client.post("/v1/chat/completions", json=body).status_code == 401
    bad = dict(body, model="gpt-4o")
    assert client.post("/v1/chat/completions", json=bad, headers=h).status_code == 400


def test_unknown_probability_is_none_without_checker():
    nop = FakeBackend("gemma-q4", {("tr", "en"): {"Merhaba dünya": "Hello world"}}, prob=None)
    r = Engine(backends=[nop], checker=FakeChecker(enabled=False)).translate("Merhaba dünya", "en", "tr")
    assert r.translation == "Hello world" and r.confidence is None


def test_gemma_prompt_format():
    from glyphbridge.backends import gemma_prompt
    p = gemma_prompt("Merhaba", "tr", "en")
    assert p.startswith("<start_of_turn>user\n") and p.endswith("<start_of_turn>model\n")
    assert "Turkish (tr) to English (en)" in p and "Merhaba" in p


def test_small_cards_are_default_order(monkeypatch):
    from glyphbridge.backends import default_backends
    monkeypatch.delenv("GLYPHBRIDGE_BACKENDS", raising=False)
    assert [b.name for b in default_backends()] == ["hymt2-q4", "opus", "gemma-q4", "gemma", "opus-group", "madlad-int8", "madlad"]


def test_rate_limit(eng):
    client = TestClient(create_app(engine=eng, api_key="", rate_limit=2))
    body = {"text": "Merhaba dünya", "source": "tr", "target": "en"}
    assert client.post("/v1/translate", json=body).status_code == 200
    assert client.post("/v1/translate", json=body).status_code == 200
    res = client.post("/v1/translate", json=body)
    assert res.status_code == 429 and int(res.headers["Retry-After"]) > 0
    assert client.get("/v1/health").status_code == 200   # health is never limited


def test_router_prefers_quality_and_respects_ram(monkeypatch):
    fast = FakeBackend("opus", {("tr", "en"): {"Merhaba dünya": "fast"}})
    good = FakeBackend("gemma-q4", {("tr", "en"): {"Merhaba dünya": "good"}})
    huge = FakeBackend("madlad", {("tr", "en"): {"Merhaba dünya": "huge"}})
    fast.ram_mb, good.ram_mb, huge.ram_mb = 600, 3500, 6500
    e = Engine(backends=[fast, good, huge], checker=FakeChecker())
    monkeypatch.setenv("GLYPHBRIDGE_RAM_BUDGET_MB", "4000")
    monkeypatch.delenv("GLYPHBRIDGE_PREFER", raising=False)
    assert [b.name for b in e._ordered()] == ["opus", "gemma-q4", "madlad"]
    monkeypatch.setenv("GLYPHBRIDGE_PREFER", "quality")
    assert e.translate("Merhaba dünya", "en", "tr").translation == "good"
    monkeypatch.setenv("GLYPHBRIDGE_RAM_BUDGET_MB", "3000")   # gemma no longer fits
    assert [b.name for b in e._ordered()] == ["opus", "gemma-q4", "madlad"]  # both big cards go last


def test_result_cache_translates_repeats_once():
    calls = []

    class Counting(FakeBackend):
        def translate(self, texts, s, t):
            calls.append(list(texts))
            return super().translate(texts, s, t)

    e = Engine(backends=[Counting("opus", OPUS.table)], checker=FakeChecker())
    out = e.translate_batch(["Merhaba dünya", "Nasılsın?", "Merhaba dünya"], target="en", source="tr")
    assert [r.translation for r in out] == ["Hello world", "How are you?", "Hello world"]
    assert calls == [["Merhaba dünya", "Nasılsın?"]]          # the repeat was not translated again
    e.translate_batch(["Nasılsın?"], target="en", source="tr")
    assert len(calls) == 1                                       # served from the cache


def test_consistency_catches_numbers_and_names():
    from glyphbridge.checker import consistency
    assert consistency("Toplantı 14:30'da, 1.500 kişi.", "The meeting is at 14:30, 1,500 people.") == []
    assert consistency("Fiyat 250 lira.", "The price is 25 lira.") == ["number 250 missing"]
    assert consistency("Dün Ahmet'in evine gittik.", "Yesterday we went to Ahmet's house.") == []
    assert consistency("Dün Ahmet'in evine gittik.", "Yesterday we went to his house.") == ["name Ahmet missing"]
    assert consistency("Москва большая.", "Moscow is big.") == []          # different scripts: names skipped


def test_engine_flags_wrong_number_even_with_high_similarity():
    wrong = FakeBackend("opus", {("tr", "en"): {"250 lira": "25 lira"}})
    right = FakeBackend("madlad", {("tr", "en"): {"250 lira": "250 lira"}})
    r = Engine(backends=[wrong, right], checker=FakeChecker()).translate("250 lira", "en", "tr")
    assert r.translation == "250 lira" and not r.flagged and r.model == "madlad:tr-en"
    r = Engine(backends=[wrong], checker=FakeChecker()).translate("250 lira", "en", "tr")
    assert r.flagged and r.issues == ["number 250 missing"]


def test_all_non_opus_cards_are_pinned():
    from glyphbridge.cards import CARDS
    for card in CARDS.values():
        assert card.revision and len(card.revision) == 40, card.id


def test_card_licenses_allow_free_commercial_use():
    """Default cards must be usable commercially; opt-in cards may carry model terms."""
    from glyphbridge.cards import CARDS
    open_licenses = {"Apache-2.0", "MIT", "CC-BY-4.0", "BSD-3-Clause"}
    opt_in = {"gemma", "gemma-q4"}        # Gemma terms: allow commercial use with a use policy
    for card in CARDS.values():
        assert card.license in open_licenses or card.id in opt_in, (card.id, card.license)
        assert "NC" not in card.license and "GPL" not in card.license, card.id


def test_cache_key_includes_models_and_settings(monkeypatch):
    calls = []

    class Counting(FakeBackend):
        def translate(self, texts, s, t):
            calls.append(self.name)
            return super().translate(texts, s, t)

    e = Engine(backends=[Counting("opus", OPUS.table)], checker=FakeChecker())
    e.translate("Merhaba dünya", "en", "tr")
    e.translate("  Merhaba   dünya ", "en", "tr")            # same text after normalization
    assert calls == ["opus"]
    monkeypatch.setenv("GLYPHBRIDGE_PREFER", "quality")      # setting changed -> not reused
    e.translate("Merhaba dünya", "en", "tr")
    assert calls == ["opus", "opus"]
    e.backends = [Counting("gemma-q4", OPUS.table)]           # different model -> not reused
    assert e.translate("Merhaba dünya", "en", "tr").model == "gemma-q4:tr-en"


def test_checksum_verification(tmp_path, monkeypatch):
    import hashlib
    import sys
    import types
    from glyphbridge import cards
    f = tmp_path / "model.bin"
    f.write_bytes(b"weights")
    good = hashlib.sha256(b"weights").hexdigest()
    fake_hub = types.SimpleNamespace(hf_hub_download=lambda repo, name, revision=None: str(f))
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    card = cards.Card("t", "test", "x/y", 1, "1", "MIT", revision="0" * 40, sha256=(("model.bin", good),))
    monkeypatch.setitem(cards.CARDS, "t", card)
    assert cards.verify("t") == ["model.bin"]
    monkeypatch.setitem(cards.CARDS, "t", cards.Card("t", "test", "x/y", 1, "1", "MIT", revision="0" * 40,
                                                     sha256=(("model.bin", "0" * 64),)))
    with pytest.raises(cards.ChecksumError):
        cards.verify("t")


def test_community_cards_have_checksums():
    from glyphbridge.cards import CARDS
    for cid in ("madlad-int8", "gemma-q4", "lid"):
        assert CARDS[cid].sha256 and all(len(h) == 64 for _, h in CARDS[cid].sha256), cid


def test_golden_script_reports_categories(tmp_path, monkeypatch):
    import importlib.util
    import json
    pytest.importorskip("sacrebleu")
    v1 = tmp_path / "v1"
    v1.mkdir()
    (v1 / "tr-en.tsv").write_text("# header\nnames\tAhmet geldi.\tAhmet came.\n"
                                  "numbers\t3 elma\t3 apples\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("golden", "scripts/golden.py")
    golden = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(golden)
    import glyphbridge.engine as eng
    answers = {"Ahmet geldi.": "Ahmet came.", "3 elma": "three apples"}

    class FakeEngine:
        def translate_batch(self, texts, target, source=None):
            return [eng.TranslationResult(answers[t], source, target, None, "fake") for t in texts]

    monkeypatch.setattr(eng, "Engine", FakeEngine)
    out = tmp_path / "r.json"
    assert golden.main([str(v1 / "tr-en.tsv") + ":0", "--json", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["version"] == "golden-v1"
    cats = report["files"]["tr-en"]["categories"]
    assert set(cats) == {"names", "numbers"} and cats["names"]["chrf"] == 100.0
    assert golden.main([str(v1 / "tr-en.tsv") + ":99"]) == 1


def test_default_router_order_is_locked(monkeypatch):
    # The fixed order is a documented contract (CONTRIBUTING: "How cards are chosen").
    # Change it only together with benchmark numbers.
    from glyphbridge.backends import ModelCache, default_backends, names
    monkeypatch.delenv("GLYPHBRIDGE_BACKENDS", raising=False)
    assert names(default_backends(ModelCache(budget_mb=1))) == ["hymt2-q4", "opus", "gemma-q4", "gemma", "opus-group", "madlad-int8", "madlad"]


def test_madlad_int8_calls_ctranslate2_with_valid_arguments():
    # Mirrors the keyword arguments ctranslate2.Translator.translate_batch accepts, so an
    # unknown argument (like the old normalize_scores) fails here and not only in CI.
    from glyphbridge.backends import MadladInt8Backend, ModelCache

    class Hyp:
        hypotheses = [["\u2581Hello"]]
        scores = [-0.1]

    class FakeTranslator:
        def translate_batch(self, source, target_prefix=None, *, max_batch_size=0, beam_size=2,
                            max_decoding_length=256, return_scores=False, length_penalty=1,
                            num_hypotheses=1, max_input_length=1024):
            return [Hyp() for _ in source]

    class FakeSP:
        def encode(self, text, out_type=str):
            return text.split()

        def decode(self, pieces):
            return "".join(pieces).replace("\u2581", " ").strip()

    b = MadladInt8Backend(ModelCache(budget_mb=100000))
    b._load = lambda: (FakeTranslator(), FakeSP())
    (text, p), = b.translate(["Merhaba"], "tr", "en")
    assert text == "Hello" and 0 < p <= 1


def test_consistency_accepts_exonyms_and_accents_but_catches_dropped_names():
    from glyphbridge.checker import consistency
    # False alarms seen in the golden-v1 CI run.
    assert consistency("Ahmet'in kız kardeşi İstanbul'da yaşıyor.", "Ahmet's sister lives in Istanbul.") == []
    assert consistency("Ankara, Türkiye'nin başkentidir.", "Ankara is the capital of Turkey.") == []
    assert consistency("Please call me before Friday.", "Lütfen cumadan önce beni ara.") == []
    # Real problems are still caught.
    assert consistency("Elif yarın Londra'ya uçacak.", "Elif will fly to Paris tomorrow.") == ["name Londra missing"]
    assert consistency("Yesterday Maria was in Berlin.", "Dün Anna Berlin'deydi.") == ["name Maria missing"]


def test_backend_that_crashes_in_supports_is_skipped():
    class Exploding(FakeBackend):
        def supports(self, s, t):
            raise RuntimeError("cache scan failed")

    e = Engine(backends=[Exploding("bad", {}), OPUS], checker=FakeChecker())
    r = e.translate("Merhaba dünya", target="en", source="tr")
    assert r.translation == "Hello world" and r.model == "opus:tr-en"


def test_opus_offline_only_considers_installed_pairs(monkeypatch):
    from glyphbridge import backends as bk
    monkeypatch.setenv("GLYPHBRIDGE_OFFLINE", "1")
    monkeypatch.setattr(bk, "_cached_repos", lambda: {"Helsinki-NLP/opus-mt-tr-en"})
    tried = []
    b = bk.OpusBackend(bk.ModelCache(budget_mb=100000))
    b._load_named = lambda name: tried.append(name) or ("tok", "model")
    assert b.supports("tr", "en") and tried == ["Helsinki-NLP/opus-mt-tr-en"]
    tried.clear()
    assert not b.supports("la", "en") and tried == []


def test_consistency_findings_from_gemma_golden_run():
    from glyphbridge.checker import consistency
    # 24-hour vs 12-hour clock is the same time.
    assert consistency("Toplantı saat 14:30'da başlayacak.", "The meeting will begin at 2:30 p.m.") == []
    assert consistency("Toplantı saat 14:30'da.", "The meeting is at 3:30 p.m.") != []
    # Month names are not names.
    assert consistency("Sözleşme 15 Mart 2025'te sona eriyor.", "The contract expires on 15 March 2025.") == []
    # A sentence written twice is caught.
    out = consistency("Sözleşme 15 Mart 2025'te sona eriyor.",
                      "The contract expires on 15 March 2025. The contract expires on 15 March 2025.")
    assert out and out[0].startswith("repeated text")


def test_gemma_routes_latin_by_default(monkeypatch):
    from glyphbridge.backends import GEMMA_DEFAULT_LANGS
    assert "la" in GEMMA_DEFAULT_LANGS


def test_translation_memory_wins_before_models(tmp_path):
    from glyphbridge.memory import Memory
    mem = tmp_path / "idioms.tsv"
    mem.write_text("# src\ttgt\tsource\ttranslation\n"
                   "tr\ten\tGözden ırak olan gönülden de ırak olur.\tOut of sight, out of mind.\n",
                   encoding="utf-8")
    e = Engine(backends=[OPUS], checker=FakeChecker(), memory=Memory([str(mem)]))
    r = e.translate_batch(["gözden ırak olan  gönülden de ırak olur", "Merhaba dünya"], target="en", source="tr")
    assert r[0].translation == "Out of sight, out of mind." and r[0].model == "memory" and not r[0].flagged
    assert r[1].translation == "Hello world" and r[1].model == "opus:tr-en"
    # Other direction is not matched.
    assert e.memory.get("Gözden ırak olan gönülden de ırak olur.", "tr", "de") is None


def test_translation_memory_rejects_bad_rows(tmp_path):
    from glyphbridge.memory import Memory
    bad = tmp_path / "bad.tsv"
    bad.write_text("tr\ten\tonly three columns\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bad.tsv:1"):
        Memory([str(bad)])


def test_cli_memory_option_sets_env(tmp_path, monkeypatch):
    from glyphbridge import cli
    import os
    monkeypatch.setenv("GLYPHBRIDGE_MEMORY", "")   # so monkeypatch restores it after main() writes it
    monkeypatch.delenv("GLYPHBRIDGE_MEMORY")
    monkeypatch.setattr(cli, "cmd_translate", lambda args: 0, raising=False)
    parser = cli.build_parser()
    args = parser.parse_args(["translate", "x", "--to", "en", "--memory", "a.tsv", "--memory", "b.tsv"])
    assert args.memory == ["a.tsv", "b.tsv"]
    monkeypatch.setattr(cli, "build_parser", lambda: parser)
    args.func = lambda a: 0
    parser.parse_args = lambda argv=None: args
    assert cli.main([]) == 0
    assert os.environ["GLYPHBRIDGE_MEMORY"] == os.pathsep.join(["a.tsv", "b.tsv"])


def test_opus_group_model_serves_latin_to_english_only():
    from glyphbridge.backends import ModelCache, OpusBackend, OpusGroupBackend
    g = OpusGroupBackend(ModelCache(budget_mb=100000))
    assert g._names("la", "en") == ["Helsinki-NLP/opus-mt-itc-en"]
    assert g._names("la", "de") == [] and g._names("tr", "en") == []
    assert "Helsinki-NLP/opus-mt-itc-en" not in OpusBackend(ModelCache(budget_mb=1))._names("la", "en")


class FakeEmotion:
    """Tone from keywords: 'love/Hello' positive, 'hate/BAD' negative."""
    def __init__(self):
        from glyphbridge.emotion import Emotion
        self._real = Emotion()

    def enabled(self):
        return True

    def labels(self, texts):
        def one(t):
            low = t.lower()
            if "hate" in low or "nefret" in low or "bad" in low:
                return ("negative", 0.95)
            if "love" in low or "seviyorum" in low or "hello" in low or "merhaba" in low:
                return ("positive", 0.95)
            return ("neutral", 0.9)
        return [one(t) for t in texts]

    def flipped(self, a, b):
        return self._real.flipped(a, b)


def test_emotion_module_flags_tone_flip_and_tries_next_card():
    flipper = FakeBackend("flipper", {("tr", "en"): {"Seni seviyorum": "I hate you"}})
    good = FakeBackend("good", {("tr", "en"): {"Seni seviyorum": "I love you"}})
    e = Engine(backends=[flipper, good], checker=FakeChecker(), memory=None, emotion=FakeEmotion())
    r = e.translate("Seni seviyorum", target="en", source="tr")
    assert r.translation == "I love you" and r.model == "good:tr-en" and r.tone == "positive"
    assert r.attempts == ["flipper:tr-en", "good:tr-en"]


def test_emotion_flip_rules():
    from glyphbridge.emotion import Emotion
    em = Emotion()
    assert em.flipped(("positive", 0.9), ("negative", 0.8)) == "tone changed: positive -> negative"
    assert em.flipped(("positive", 0.9), ("neutral", 0.99)) is None      # softer is not a flip
    assert em.flipped(("positive", 0.55), ("negative", 0.9)) is None     # unsure source
    assert em.flipped(None, ("negative", 0.9)) is None


def test_emotion_module_is_off_without_card(monkeypatch):
    from glyphbridge import cards
    from glyphbridge.emotion import Emotion
    monkeypatch.delenv("GLYPHBRIDGE_EMOTION", raising=False)
    monkeypatch.setattr(cards, "is_installed", lambda repo, cached=None: False)
    assert Emotion().labels(["x", "y"]) == [None, None]
    monkeypatch.setenv("GLYPHBRIDGE_EMOTION", "0")
    monkeypatch.setattr(cards, "is_installed", lambda repo, cached=None: True)
    assert not Emotion().enabled()


def test_hymt2_card_is_pinned_and_off_by_default(monkeypatch):
    from glyphbridge import backends as bk
    from glyphbridge.cards import CARDS
    c = CARDS["hymt2-q4"]
    assert c.license == "Apache-2.0" and len(c.revision) == 40 and c.sha256
    monkeypatch.delenv("GLYPHBRIDGE_ENABLE_HYMT", raising=False)
    monkeypatch.setattr(bk, "is_installed", lambda repo, cached=None: False)
    b = bk.HyMT2Q4Backend(bk.ModelCache(budget_mb=100000))
    assert not b.supports("tr", "en")
    monkeypatch.setenv("GLYPHBRIDGE_ENABLE_HYMT", "1")
    assert b.supports("tr", "en") and not b.supports("la", "en")
    assert "into Turkish" in b.prompt("Hello", "tr")


def test_golden_sets_are_well_formed_and_v2_keeps_v1():
    # A released set must never change: golden-v2 starts with every golden-v1 row, unchanged.
    import pathlib
    root = pathlib.Path(__file__).parent / "golden"
    known = {"general", "questions", "names", "numbers", "dates", "negation", "idioms",
             "technical", "medical", "formal", "morphology", "long", "low-resource"}

    def rows(path):
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                parts = line.split("\t")
                assert len(parts) == 3, (path.name, line)
                assert parts[0] in known, (path.name, parts[0])
                assert parts[1].strip() and parts[2].strip(), (path.name, line)
                out.append(tuple(parts))
        return out

    for version in ("v1", "v2"):
        for path in sorted((root / version).glob("*.tsv")):
            r = rows(path)
            assert len({s for _, s, _ in r}) == len(r), f"duplicate source in {version}/{path.name}"
    for path in sorted((root / "v1").glob("*.tsv")):
        old, new = rows(path), rows(root / "v2" / path.name)
        assert new[:len(old)] == old, f"v2/{path.name} must start with the v1 rows"
    assert sum(len(rows(p)) for p in (root / "v2").glob("*.tsv")) >= 200
