from glyphbridge.ancient import cuneiform_name, gardiner, sign_list, signs


def test_gardiner_codes():
    assert gardiner("\U00013000") == "A1"
    assert gardiner("\U000130C0") == "D58"
    assert gardiner("\U00013171") == "G43"
    assert gardiner("\U000133E4") == "Z1"
    assert gardiner("a") is None


def test_gardiner_keeps_variant_letters():
    # Unicode names variants like "A006A"; the code keeps the letter: A6A.
    import unicodedata
    ch = unicodedata.lookup("EGYPTIAN HIEROGLYPH A006A")
    assert gardiner(ch) == "A6A"


def test_cuneiform_sign_names():
    assert cuneiform_name("\U00012000") == "A"
    assert cuneiform_name("\U00012038") == "ASH"
    assert cuneiform_name("x") is None


def test_signs_skip_other_text_and_mark_punctuation():
    found = signs("Ra: \U00013000\U000130C0 / \U00012000\U00012470")
    assert [s.code for s in found] == ["A1", "D58", "A", "OLD ASSYRIAN WORD DIVIDER"]
    assert [s.script for s in found] == ["Egyp", "Egyp", "Xsux", "Xsux"]
    assert found[-1].kind == "punctuation" and found[0].codepoint == "U+13000"


def test_sign_list_keeps_words():
    assert sign_list("\U00013000\U000130C0 \U00013171") == "A1-D58 G43"
    assert sign_list("\U00012000\U00012038\U00012470") == "A-ASH"
    assert sign_list("hello") == ""


def test_cli_signs(capsys):
    from glyphbridge import cli
    assert cli.main(["signs", "\U00013000\U000130C0"]) == 0
    assert capsys.readouterr().out.strip() == "A1-D58"
    assert cli.main(["signs", "hello"]) == 1
