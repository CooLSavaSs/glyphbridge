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
