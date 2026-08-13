from rmstory import render
from rmstory.run import resolve_run


def test_rewrite_spans_preserves_everything_else(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(
        '<p>Intro</p>\n<span lang="en" id="greeting">Hello</span>\n<p>Outro</p>',
        encoding="utf-8",
    )
    spans = resolve_run([path])

    result = render.rewrite_spans(path, spans, {"greeting": ("Hola", "es")})

    assert result == '<p>Intro</p>\n<span lang="es" id="greeting">Hola</span>\n<p>Outro</p>'


def test_rewrite_spans_leaves_unreplaced_spans_alone(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(
        '<span lang="en" id="a">A</span><span lang="en" id="b">B</span>', encoding="utf-8"
    )
    spans = resolve_run([path])

    result = render.rewrite_spans(path, spans, {"a": ("Ah", "es")})

    assert result == '<span lang="es" id="a">Ah</span><span lang="en" id="b">B</span>'


def test_rewrite_spans_preserves_nested_markup_in_untouched_spans(tmp_path):
    path = tmp_path / "a.md"
    path.write_text('<span lang="en" id="a">Hello <b>world</b></span>', encoding="utf-8")
    spans = resolve_run([path])

    result = render.rewrite_spans(path, spans, {})

    assert result == '<span lang="en" id="a">Hello <b>world</b></span>'


def test_assemble_story_orders_and_flags_missing(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(
        '<span lang="en" id="x">First</span><span lang="en" id="y">Second</span>',
        encoding="utf-8",
    )
    spans = resolve_run([path])
    spans_by_id = {span.id: span for span in spans}

    text, missing = render.assemble_story(spans_by_id, ["y", "x", "z"])

    assert text == "Second\n\nFirst"
    assert missing == ["z"]
