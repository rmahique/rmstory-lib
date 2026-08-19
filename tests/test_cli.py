from typing import ClassVar

from rmstory import engines
from rmstory.cli import main
from rmstory.storage import translations


def _use_filesystem_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("MULTILANG_DB_BACKEND", "filesystem")
    monkeypatch.setenv("MULTILANG_DB_PATH", str(tmp_path / "strings"))


class _FakeEngine:
    """A no-network TranslationEngine registered as "fake-test" for CLI
    tests to exercise --engine wiring without needing real credentials or
    an SDK. Records every call on the class so tests can assert on it
    regardless of which internal instance the CLI happened to construct.
    """

    calls: ClassVar[list] = []
    SUPPORTS_GENERATION = False

    def translate(self, text, from_lang, to_lang):
        _FakeEngine.calls.append((text, from_lang, to_lang))
        return "[{}] {}".format(to_lang.upper(), text)


def _use_fake_engine(monkeypatch):
    _FakeEngine.calls = []
    monkeypatch.setitem(engines._ENGINES, "fake-test", _FakeEngine)


class _FakeGenerationEngine:
    """A no-network, SUPPORTS_GENERATION=True engine registered as
    "fake-gen" for CLI tests to exercise `generate rewrite`/`generate new`
    wiring without real credentials or an SDK."""

    calls: ClassVar[list] = []
    SUPPORTS_GENERATION = True
    response = ""

    def generate(self, prompt):
        _FakeGenerationEngine.calls.append(prompt)
        return _FakeGenerationEngine.response


def _use_fake_generation_engine(monkeypatch, response=""):
    _FakeGenerationEngine.calls = []
    _FakeGenerationEngine.response = response
    monkeypatch.setitem(engines._ENGINES, "fake-gen", _FakeGenerationEngine)


def test_extract_then_translate_single_file_to_stdout(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en" id="greeting">Hello</span>', encoding="utf-8")

    assert main(["extract", str(src), "--stories-dir", str(tmp_path / "stories")]) == 0
    capsys.readouterr()  # discard extract's own stdout

    conn = translations.connect()
    translations.store(conn, "greeting", "es", "Hola")

    rc = main(["translate", str(src), "--to", "es"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out == '<span lang="es" id="greeting">Hola</span>'


def test_translate_missing_translation_hard_fails(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en" id="greeting">Hello</span>', encoding="utf-8")

    rc = main(["translate", str(src), "--to", "fr"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "greeting" in err
    assert "--engine" in err
    assert "gemini" in err  # one of the registered engine names, listed as a hint


def test_translate_multi_file_requires_out(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    (tmp_path / "a.md").write_text('<span lang="en" id="a">A</span>', encoding="utf-8")
    (tmp_path / "b.md").write_text('<span lang="en" id="b">B</span>', encoding="utf-8")

    rc = main(["translate", str(tmp_path), "--to", "es"])
    assert rc == 1
    assert "--out" in capsys.readouterr().err


def test_extract_then_story(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text(
        '<span lang="en" id="a" hist="arc">First</span>'
        '<span lang="en" id="b" hist="arc">Second</span>',
        encoding="utf-8",
    )
    stories_dir = tmp_path / "stories"

    assert main(["extract", str(src), "--stories-dir", str(stories_dir)]) == 0
    capsys.readouterr()  # discard extract's own stdout

    rc = main(["story", str(src), "--story", "arc", "--stories-dir", str(stories_dir)])
    out = capsys.readouterr().out
    assert rc == 0
    assert out == "First\n\nSecond"


def test_story_missing_entry_hard_fails(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    (stories_dir / "arc.yaml").write_text("- ghost-id\n", encoding="utf-8")
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en" id="a">A</span>', encoding="utf-8")

    rc = main(["story", str(src), "--story", "arc", "--stories-dir", str(stories_dir)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "ghost-id" in err


def test_translate_engine_fills_missing_translation(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    _use_fake_engine(monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en" id="greeting">Hello</span>', encoding="utf-8")

    rc = main(["translate", str(src), "--to", "es", "--engine", "fake-test"])
    out = capsys.readouterr().out

    assert rc == 0
    assert out == '<span lang="es" id="greeting">[ES] Hello</span>'
    assert _FakeEngine.calls == [("Hello", "en", "es")]


def test_translate_engine_stores_translation_for_later_runs(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    _use_fake_engine(monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en" id="greeting">Hello</span>', encoding="utf-8")

    assert main(["translate", str(src), "--to", "es", "--engine", "fake-test"]) == 0
    capsys.readouterr()

    # A second run, without --engine, should now succeed from storage alone.
    rc = main(["translate", str(src), "--to", "es"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out == '<span lang="es" id="greeting">[ES] Hello</span>'
    assert len(_FakeEngine.calls) == 1  # engine wasn't called again


def test_translate_engine_does_not_overwrite_existing_translation(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    _use_fake_engine(monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en" id="greeting">Hello</span>', encoding="utf-8")

    conn = translations.connect()
    translations.store(conn, "greeting", "es", "Hola, viajero.")

    rc = main(["translate", str(src), "--to", "es", "--engine", "fake-test"])
    out = capsys.readouterr().out

    assert rc == 0
    assert out == '<span lang="es" id="greeting">Hola, viajero.</span>'
    assert _FakeEngine.calls == []  # never called -- existing translation wins


def test_translate_unknown_engine_is_a_clean_error(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en" id="greeting">Hello</span>', encoding="utf-8")

    rc = main(["translate", str(src), "--to", "es", "--engine", "no-such-engine"])
    err = capsys.readouterr().err

    assert rc == 1
    assert "no-such-engine" in err


def test_extract_to_without_engine_is_an_error(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en" id="greeting">Hello</span>', encoding="utf-8")

    rc = main(["extract", str(src), "--to", "es"])
    err = capsys.readouterr().err

    assert rc == 1
    assert "--engine" in err


def test_extract_with_engine_autofills_target_languages(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    _use_fake_engine(monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en" id="greeting">Hello</span>', encoding="utf-8")

    rc = main(
        [
            "extract",
            str(src),
            "--stories-dir",
            str(tmp_path / "stories"),
            "--engine",
            "fake-test",
            "--to",
            "es",
            "--to",
            "fr",
        ]
    )
    assert rc == 0
    assert sorted(_FakeEngine.calls) == sorted(
        [("Hello", "en", "es"), ("Hello", "en", "fr")]
    )

    conn = translations.connect()
    assert translations.fetch(conn, "greeting", "es") == "[ES] Hello"
    assert translations.fetch(conn, "greeting", "fr") == "[FR] Hello"
    assert translations.fetch(conn, "greeting", "en") == "Hello"  # source untouched


def test_extract_assigns_missing_nested_id_derived_from_parent(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text(
        '<span lang="en" id="para">Hi <span no>World</span> there</span>', encoding="utf-8"
    )

    rc = main(["extract", str(src), "--stories-dir", str(tmp_path / "stories")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "assigned 1 id(s)" in out

    rewritten = src.read_text(encoding="utf-8")
    assert rewritten == (
        '<span lang="en" id="para">Hi <span id="para.1" no>World</span> there</span>'
    )


def test_extract_reuses_id_for_matching_content(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text(
        '<span lang="en" id="a">Hi <span no id="hero">Aldric</span> there</span>'
        '<span lang="en" id="b">Bye <span no>Aldric</span> now</span>',
        encoding="utf-8",
    )

    assert main(["extract", str(src), "--stories-dir", str(tmp_path / "stories")]) == 0

    rewritten = src.read_text(encoding="utf-8")
    assert rewritten == (
        '<span lang="en" id="a">Hi <span no id="hero">Aldric</span> there</span>'
        '<span lang="en" id="b">Bye <span id="hero" no>Aldric</span> now</span>'
    )


def test_extract_auto_id_is_idempotent(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text(
        '<span lang="en" id="para">Hi <span no>World</span> there</span>', encoding="utf-8"
    )

    assert main(["extract", str(src), "--stories-dir", str(tmp_path / "stories")]) == 0
    capsys.readouterr()
    once = src.read_text(encoding="utf-8")

    rc = main(["extract", str(src), "--stories-dir", str(tmp_path / "stories")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "assigned" not in out
    assert src.read_text(encoding="utf-8") == once


def test_extract_doubly_nested_both_missing_id(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text(
        '<span lang="en" id="a">x<span no>y<span no>z</span></span></span>', encoding="utf-8"
    )

    rc = main(["extract", str(src), "--stories-dir", str(tmp_path / "stories")])
    assert rc == 0

    rewritten = src.read_text(encoding="utf-8")
    assert rewritten == (
        '<span lang="en" id="a">x<span id="a.1" no>y<span id="a.1.1" no>z</span></span></span>'
    )


def test_extract_assigns_missing_top_level_id_derived_from_filename(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en">no id here</span>', encoding="utf-8")

    rc = main(["extract", str(src), "--stories-dir", str(tmp_path / "stories")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "assigned 1 id(s)" in out
    assert src.read_text(encoding="utf-8") == '<span id="doc.1" lang="en">no id here</span>'


def test_validate_still_hard_fails_on_missing_top_level_id(tmp_path, monkeypatch, capsys):
    # extract auto-assigns; every other command still doesn't.
    _use_filesystem_backend(tmp_path, monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en">no id here</span>', encoding="utf-8")

    rc = main(["validate", str(src)])
    assert rc == 1


def test_extract_with_engine_skips_already_stored_translation(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    _use_fake_engine(monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en" id="greeting">Hello</span>', encoding="utf-8")

    conn = translations.connect()
    translations.store(conn, "greeting", "es", "Hola, viajero.")

    rc = main(
        [
            "extract",
            str(src),
            "--stories-dir",
            str(tmp_path / "stories"),
            "--engine",
            "fake-test",
            "--to",
            "es",
        ]
    )
    assert rc == 0
    assert _FakeEngine.calls == []  # existing "es" row was never touched
    assert translations.fetch(conn, "greeting", "es") == "Hola, viajero."


def test_generate_rewrite_single_file_to_stdout(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    response = "===[greeting]===\nWelcome, wanderer."
    _use_fake_generation_engine(monkeypatch, response=response)
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en" id="greeting">Hello</span>', encoding="utf-8")

    rc = main(["generate", "rewrite", str(src), "--engine", "fake-gen"])
    out = capsys.readouterr().out

    assert rc == 0
    assert out == '<span lang="en" id="greeting">Welcome, wanderer.</span>'


def test_generate_rewrite_passes_theme_into_prompt(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    _use_fake_generation_engine(monkeypatch, response="===[greeting]===\nHi.")
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en" id="greeting">Hello</span>', encoding="utf-8")

    rc = main(
        ["generate", "rewrite", str(src), "--engine", "fake-gen", "--theme", "a haunted lighthouse"]
    )
    capsys.readouterr()

    assert rc == 0
    assert "a haunted lighthouse" in _FakeGenerationEngine.calls[0]


def test_generate_rewrite_with_engine_that_doesnt_support_generation(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    _use_fake_engine(monkeypatch)
    src = tmp_path / "doc.md"
    src.write_text('<span lang="en" id="greeting">Hello</span>', encoding="utf-8")

    rc = main(["generate", "rewrite", str(src), "--engine", "fake-test"])
    err = capsys.readouterr().err

    assert rc == 1
    assert "fake-test" in err
    assert "doesn't support story generation" in err


def test_generate_rewrite_multiple_files_requires_out(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    _use_fake_generation_engine(monkeypatch, response="===[a]===\nx")
    (tmp_path / "one.md").write_text('<span lang="en" id="a">Hello</span>', encoding="utf-8")
    (tmp_path / "two.md").write_text('<span lang="en" id="b">World</span>', encoding="utf-8")

    rc = main(["generate", "rewrite", str(tmp_path), "--engine", "fake-gen"])
    err = capsys.readouterr().err

    assert rc == 1
    assert "--out" in err


def test_generate_rewrite_writes_out_dir(tmp_path, monkeypatch, capsys):
    _use_filesystem_backend(tmp_path, monkeypatch)
    _use_fake_generation_engine(monkeypatch, response="===[a]===\nNew text.")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "one.md").write_text('<span lang="en" id="a">Hello</span>', encoding="utf-8")
    out_dir = tmp_path / "out"

    rc = main(["generate", "rewrite", str(src_dir), "--engine", "fake-gen", "--out", str(out_dir)])
    capsys.readouterr()

    assert rc == 0
    assert (out_dir / "one.md").read_text(encoding="utf-8") == '<span lang="en" id="a">New text.</span>'


def test_generate_new_writes_stdout(monkeypatch, capsys):
    _use_fake_generation_engine(
        monkeypatch, response='<span lang="en" id="ch1.a">Once upon a time.</span>'
    )

    rc = main(["generate", "new", "--engine", "fake-gen", "--prompt", "a lighthouse keeper"])
    out = capsys.readouterr().out

    assert rc == 0
    assert out == '<span lang="en" id="ch1.a">Once upon a time.</span>'
    assert "a lighthouse keeper" in _FakeGenerationEngine.calls[0]


def test_generate_new_writes_out_file(tmp_path, monkeypatch, capsys):
    _use_fake_generation_engine(monkeypatch, response='<span lang="en" id="ch1.a">Text.</span>')
    out_file = tmp_path / "new-story.md"

    rc = main(
        ["generate", "new", "--engine", "fake-gen", "--prompt", "a lighthouse keeper", "--out", str(out_file)]
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert "wrote" in out
    assert out_file.read_text(encoding="utf-8") == '<span lang="en" id="ch1.a">Text.</span>'


def test_generate_new_with_engine_that_doesnt_support_generation(monkeypatch, capsys):
    _use_fake_engine(monkeypatch)

    rc = main(["generate", "new", "--engine", "fake-test", "--prompt", "a lighthouse keeper"])
    err = capsys.readouterr().err

    assert rc == 1
    assert "doesn't support story generation" in err
