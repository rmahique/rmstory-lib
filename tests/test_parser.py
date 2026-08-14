import pytest

from rmstory.exceptions import ValidationError
from rmstory.parser import scan_file


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_scans_translatable_span(tmp_path):
    path = _write(tmp_path, "a.md", '<span lang="es" id="greeting">Hola</span>')
    spans = scan_file(path)
    assert len(spans) == 1
    assert spans[0].id == "greeting"
    assert spans[0].lang == "es"
    assert spans[0].hist is None
    assert spans[0].no is False
    assert spans[0].content == "Hola"


def test_no_is_boolean(tmp_path):
    path = _write(tmp_path, "a.md", '<span lang="es" id="x" no>Fixed</span>')
    spans = scan_file(path)
    assert spans[0].no is True


def test_untagged_span_ignored(tmp_path):
    path = _write(tmp_path, "a.md", '<span class="foo">plain</span>')
    assert scan_file(path) == []


def test_hist_without_value_hard_fails(tmp_path):
    path = _write(tmp_path, "a.md", '<span lang="es" id="x" hist>oops</span>')
    with pytest.raises(ValidationError):
        scan_file(path)


def test_nested_tagged_span_becomes_its_own_span_with_placeholder_in_parent(tmp_path):
    path = _write(
        tmp_path,
        "a.md",
        '<span lang="en" id="outer">Once upon a time, '
        '<span no id="hero-name">Aldric</span> ventured forth.</span>',
    )
    spans = scan_file(path)
    assert len(spans) == 2

    outer = next(s for s in spans if s.id == "outer")
    inner = next(s for s in spans if s.id == "hero-name")

    assert outer.parent_id is None
    assert outer.content == 'Once upon a time, <span id="hero-name"/> ventured forth.'
    assert inner.parent_id == "outer"
    assert inner.content == "Aldric"
    assert inner.no is True


def test_nested_span_appears_after_parent_in_document_order(tmp_path):
    # A nested span's closing tag is hit before its parent's -- scan_file
    # must still return document (opening-tag) order, so a parent always
    # precedes its own nested children.
    path = _write(
        tmp_path,
        "a.md",
        '<span lang="en" id="outer">a <span no id="inner">b</span> c</span>',
    )
    spans = scan_file(path)
    assert [s.id for s in spans] == ["outer", "inner"]


def test_doubly_nested_span(tmp_path):
    path = _write(
        tmp_path,
        "a.md",
        '<span lang="en" id="a">x'
        '<span no id="b">y<span no id="c">z</span></span>'
        "</span>",
    )
    spans = scan_file(path)
    by_id = {s.id: s for s in spans}
    assert by_id["a"].parent_id is None
    assert by_id["a"].content == 'x<span id="b"/>'
    assert by_id["b"].parent_id == "a"
    assert by_id["b"].content == 'y<span id="c"/>'
    assert by_id["c"].parent_id == "b"
    assert by_id["c"].content == "z"


def test_nested_span_without_id_hard_fails(tmp_path):
    path = _write(
        tmp_path,
        "a.md",
        '<span lang="en" id="outer">a <span no>b</span> c</span>',
    )
    with pytest.raises(ValidationError):
        scan_file(path)


def test_lenient_mode_allows_missing_nested_id(tmp_path):
    path = _write(
        tmp_path,
        "a.md",
        '<span lang="en" id="outer">a <span no>b</span> c</span>',
    )
    spans = scan_file(path, strict=False)
    outer = next(s for s in spans if s.id == "outer")
    inner = next(s for s in spans if s.id is None)
    assert inner.content == "b"
    assert inner.parent_id == "outer"  # the *parent* has a real id
    assert inner.parent_tag_start == outer.tag_start


def test_lenient_mode_parent_tag_start_survives_missing_parent_id(tmp_path):
    # When the *enclosing* span is also missing an id, parent_id can't
    # identify it (nothing to put there) -- parent_tag_start still can,
    # unambiguously, by position. This is what lets cli.py's auto-id
    # pre-pass resolve a chain of several id-less nested levels in order.
    path = _write(
        tmp_path,
        "a.md",
        '<span lang="en" id="outer">a <span no>b <span no>c</span></span></span>',
    )
    spans = scan_file(path, strict=False)
    mid = next(s for s in spans if s.content.startswith("b"))
    inner = next(s for s in spans if s.content == "c")
    assert mid.id is None
    assert inner.parent_id is None  # mid has no id, so this can't name it
    assert inner.parent_tag_start == mid.tag_start  # but this still can


def test_lenient_mode_still_hard_fails_on_other_errors(tmp_path):
    path = _write(
        tmp_path,
        "a.md",
        '<span lang="en" id="outer">a <span no hist>b</span> c</span>',
    )
    with pytest.raises(ValidationError):
        scan_file(path, strict=False)


def test_unclosed_nested_span_hard_fails(tmp_path):
    path = _write(
        tmp_path,
        "a.md",
        '<span lang="en" id="outer">a <span no id="inner">b</span>',
    )
    with pytest.raises(ValidationError):
        scan_file(path)


def test_nested_span_sibling_of_untracked_tag(tmp_path):
    # An untracked tag (<b>) at the same level as a nested tracked span
    # must not confuse the per-frame untracked-depth tracking.
    path = _write(
        tmp_path,
        "a.md",
        '<span lang="en" id="outer"><b>bold</b> <span no id="inner">x</span></span>',
    )
    spans = scan_file(path)
    by_id = {s.id: s for s in spans}
    assert by_id["inner"].content == "x"
    # the untracked <b>...</b> markup itself isn't preserved in content
    # (pre-existing limitation for untracked nested tags, unchanged here)
    assert by_id["outer"].content == 'bold <span id="inner"/>'


def test_non_utf8_file_hard_fails(tmp_path):
    path = tmp_path / "a.md"
    path.write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(ValidationError):
        scan_file(path)
