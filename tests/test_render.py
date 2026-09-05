import pytest

from rmstory import render
from rmstory.exceptions import ValidationError
from rmstory.run import resolve_run


def test_rewrite_spans_duplicate_id_each_span_renders_its_own_position(tmp_path):
    # Two different, differently-positioned spans can legitimately share an
    # id (e.g. extract's content-match reuse). Internal caching must be
    # keyed by something per-instance (tag_start), not the shared id --
    # otherwise the second span would return the first one's cached bytes.
    path = tmp_path / "a.md"
    path.write_text(
        '<span lang="en" id="dup">First</span> middle '
        '<span lang="en" id="dup">Second</span>',
        encoding="utf-8",
    )
    spans = resolve_run([path])

    result = render.rewrite_spans(path, spans, {})

    assert result == (
        '<span lang="en" id="dup">First</span> middle '
        '<span lang="en" id="dup">Second</span>'
    )


def test_replace_lang_attr_unquoted_value_keeps_closing_bracket():
    # lang=en> (no quotes) is valid: an unquoted attribute value ends at
    # whitespace or '>'. A greedy \S+ used to swallow the '>' itself,
    # silently deleting it from the tag -- reproduces the corruption seen
    # in a real translated file (lang=en> became lang=pt, losing the '>'
    # and fusing the next word into the tag).
    tag = '<span id="x" lang=en>'
    assert render._replace_lang_attr(tag, "pt") == '<span id="x" lang=pt>'


def test_rewrite_spans_unquoted_lang_attribute_keeps_closing_bracket(tmp_path):
    path = tmp_path / "a.md"
    path.write_text('<span id="a" lang=en> tab and log in.</span>', encoding="utf-8")
    spans = resolve_run([path])

    result = render.rewrite_spans(path, spans, {"a": (" aba e faça login.", "pt")})

    assert result == '<span id="a" lang=pt> aba e faça login.</span>'


def test_rewrite_spans_reindents_multiline_replacement_to_match_source_indent(tmp_path):
    # A span living inside a YAML `contents: |` literal block scalar --
    # every line of that block must stay indented to at least the tag's
    # own level or YAML parses the rest of the document as something
    # else entirely. A translation engine only trims the outer edges of
    # what it returns (see rmstory.engines.*'s `.strip()` calls), so a
    # multi-line replacement comes back with none of the original
    # per-line indentation -- reproduces a real Instruqt YAML-corruption
    # bug where a translated span's continuation lines lost their
    # indent and broke the enclosing block scalar.
    path = tmp_path / "a.md"
    path.write_text(
        "notes:\n"
        "- type: text\n"
        "  contents: |\n"
        '    <span id="a" lang="en">Hello</span>\n'
        '    <img src="x"/>\n',
        encoding="utf-8",
    )
    spans = resolve_run([path])

    result = render.rewrite_spans(path, spans, {"a": ("Line one.\nLine two.", "es")})

    assert result == (
        "notes:\n"
        "- type: text\n"
        "  contents: |\n"
        '    <span id="a" lang="es">Line one.\n'
        "    Line two.</span>\n"
        '    <img src="x"/>\n'
    )


def test_rewrite_spans_reindents_replacement_chained_after_a_prior_span(tmp_path):
    # A span whose tag doesn't start its own line -- it's chained right
    # after a *previous* span's closing tag on the same line -- but that
    # line still sits inside an indented YAML `contents: |` block. The
    # earlier (buggy) heuristic only reindented a span sitting alone on
    # its own line, so this real-world shape (reproduces a genuine
    # Instruqt YAML break: `yaml: line N: could not find expected ':'`)
    # was missed entirely and its continuation line came back with zero
    # indentation, ending the block scalar early.
    path = tmp_path / "a.md"
    path.write_text(
        "notes:\n"
        "- type: text\n"
        "  contents: |\n"
        '    <span id="a" lang="en">First</span><span id="b" lang="en">Hello</span>\n'
        '    <img src="x"/>\n',
        encoding="utf-8",
    )
    spans = resolve_run([path])

    result = render.rewrite_spans(path, spans, {"b": ("Line one.\nLine two.", "es")})

    assert result == (
        "notes:\n"
        "- type: text\n"
        "  contents: |\n"
        '    <span id="a" lang="en">First</span><span id="b" lang="es">Line one.\n'
        "    Line two.</span>\n"
        '    <img src="x"/>\n'
    )


def test_rewrite_spans_leaves_inline_multiline_replacement_unindented(tmp_path):
    # A span that shares its line with other content (not alone on its
    # own line) has no structural indent to reproduce -- adding one
    # would be pure invention, so continuation lines are left exactly
    # as the replacement provided them.
    path = tmp_path / "a.md"
    path.write_text('Intro <span id="a" lang="en">Hello</span> outro', encoding="utf-8")
    spans = resolve_run([path])

    result = render.rewrite_spans(path, spans, {"a": ("Line one.\nLine two.", "es")})

    assert result == 'Intro <span id="a" lang="es">Line one.\nLine two.</span> outro'


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


def test_rewrite_spans_translating_parent_with_id_less_nested_span(tmp_path):
    # The nested span needs no id (bare `no`, no lang/hist) -- its
    # placeholder in the parent's stored translation uses its tag_start as
    # a positional stand-in instead, and still resolves correctly.
    path = tmp_path / "a.md"
    path.write_text(
        '<span lang="en" id="para">Once upon a time, <span no>Aldric</span> ventured forth.</span>',
        encoding="utf-8",
    )
    spans = resolve_run([path])
    inner = next(s for s in spans if s.id is None)

    result = render.rewrite_spans(
        path,
        spans,
        {"para": ('Había una vez, <span id="{}"/> se aventuró.'.format(inner.tag_start), "es")},
    )

    assert result == (
        '<span lang="es" id="para">Había una vez, '
        '<span no>Aldric</span> se aventuró.</span>'
    )


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

    text, missing = render.assemble_story(spans, ["para"])

    assert text == "Once upon a time, Aldric ventured forth."
    assert missing == []


def test_assemble_story_orders_and_flags_missing(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(
        '<span lang="en" id="x">First</span><span lang="en" id="y">Second</span>',
        encoding="utf-8",
    )
    spans = resolve_run([path])

    text, missing = render.assemble_story(spans, ["y", "x", "z"])

    assert text == "Second\n\nFirst"
    assert missing == ["z"]
