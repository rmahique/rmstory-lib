import pytest

from rmstory import render
from rmstory.exceptions import ValidationError
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


def test_rewrite_spans_translating_parent_keeps_untouched_nested_span_verbatim(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(
        '<span lang="en" id="para">Once upon a time, '
        '<span no id="hero">Aldric</span> ventured forth.</span>',
        encoding="utf-8",
    )
    spans = resolve_run([path])

    result = render.rewrite_spans(
        path,
        spans,
        {"para": ('Había una vez, <span id="hero"/> se aventuró.', "es")},
    )

    assert result == (
        '<span lang="es" id="para">Había una vez, '
        '<span no id="hero">Aldric</span> se aventuró.</span>'
    )


def test_rewrite_spans_translating_only_nested_child(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(
        '<span lang="en" id="para">Say <span lang="en" id="quote">hello</span> now.</span>',
        encoding="utf-8",
    )
    spans = resolve_run([path])

    result = render.rewrite_spans(path, spans, {"quote": ("hola", "es")})

    assert result == (
        '<span lang="en" id="para">Say <span lang="es" id="quote">hola</span> now.</span>'
    )


def test_rewrite_spans_translating_parent_and_nested_child_together(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(
        '<span lang="en" id="para">Say <span lang="en" id="quote">hello</span> now.</span>',
        encoding="utf-8",
    )
    spans = resolve_run([path])

    result = render.rewrite_spans(
        path,
        spans,
        {
            "para": ('Di <span id="quote"/> ahora.', "es"),
            "quote": ("hola", "es"),
        },
    )

    assert result == (
        '<span lang="es" id="para">Di <span lang="es" id="quote">hola</span> ahora.</span>'
    )


def test_rewrite_spans_missing_nested_placeholder_in_translation_hard_fails(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(
        '<span lang="en" id="para">Say <span lang="en" id="quote">hello</span> now.</span>',
        encoding="utf-8",
    )
    spans = resolve_run([path])

    with pytest.raises(ValidationError):
        render.rewrite_spans(
            path,
            spans,
            {
                # dropped the required <span id="quote"/> reference
                "para": ("Di ahora.", "es"),
                "quote": ("hola", "es"),
            },
        )


def test_assemble_story_resolves_nested_placeholder(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(
        '<span lang="en" hist="arc" id="para">Once upon a time, '
        '<span no id="hero">Aldric</span> ventured forth.</span>',
        encoding="utf-8",
    )
    spans = resolve_run([path])
    spans_by_id = {span.id: span for span in spans}

    text, missing = render.assemble_story(spans_by_id, ["para"])

    assert text == "Once upon a time, Aldric ventured forth."
    assert missing == []


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
