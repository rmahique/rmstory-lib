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


def test_nested_tagged_span_hard_fails(tmp_path):
    path = _write(
        tmp_path,
        "a.md",
        '<span lang="es" id="outer"><span lang="en" id="inner">x</span></span>',
    )
    with pytest.raises(ValidationError):
        scan_file(path)


def test_non_utf8_file_hard_fails(tmp_path):
    path = tmp_path / "a.md"
    path.write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(ValidationError):
        scan_file(path)
