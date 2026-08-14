import pytest

from rmstory.exceptions import ValidationError
from rmstory.run import resolve_run


def test_inheritance_across_files(tmp_path):
    """
    hist-without-lang inherits from the nearest preceding lang-tagged span
    across the whole run, not just the current file (requisites.md).
    """
    (tmp_path / "01-intro.md").write_text(
        '<span lang="es" id="intro">Hola</span>', encoding="utf-8"
    )
    (tmp_path / "02-chapter.md").write_text(
        '<span hist="villain-arc" id="reveal">Twist</span>', encoding="utf-8"
    )

    spans = resolve_run([tmp_path])
    assert len(spans) == 2
    reveal = next(s for s in spans if s.id == "reveal")
    assert reveal.language == "es"
    assert reveal.story_id == "villain-arc"


def test_nested_span_inherits_enclosing_parents_lang(tmp_path):
    (tmp_path / "a.md").write_text(
        '<span lang="es" id="para">Había una vez '
        '<span hist="villain-arc" id="reveal">un giro</span> mas.</span>',
        encoding="utf-8",
    )

    spans = resolve_run([tmp_path])
    reveal = next(s for s in spans if s.id == "reveal")
    assert reveal.parent_id == "para"
    assert reveal.language == "es"
    assert reveal.story_id == "villain-arc"
    assert reveal.translatable is True


def test_no_earlier_lang_hard_fails(tmp_path):
    (tmp_path / "a.md").write_text(
        '<span hist="villain-arc" id="reveal">Twist</span>', encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        resolve_run([tmp_path])


def test_invalid_bcp47_hard_fails(tmp_path):
    (tmp_path / "a.md").write_text(
        '<span lang="not a tag" id="x">y</span>', encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        resolve_run([tmp_path])


def test_missing_id_hard_fails(tmp_path):
    (tmp_path / "a.md").write_text('<span lang="es">y</span>', encoding="utf-8")
    with pytest.raises(ValidationError):
        resolve_run([tmp_path])
