"""
One test per row of requisites.md's truth table (`== Functioning Logic`).
"""

import pytest

from rmstory.attributes import resolve_attributes
from rmstory.exceptions import ValidationError


def test_row1_lang_only():
    r = resolve_attributes(lang="es")
    assert (r.translatable, r.language, r.story_id, r.warning) == (True, "es", None, None)


def test_row2_lang_and_hist():
    r = resolve_attributes(lang="es", hist="villain-arc")
    assert (r.translatable, r.language, r.story_id, r.warning) == (True, "es", "villain-arc", None)


def test_row3_nolang():
    r = resolve_attributes(lang="nolang")
    assert (r.translatable, r.language, r.story_id, r.warning) == (False, None, None, None)


def test_row4_nolang_and_hist():
    r = resolve_attributes(lang="nolang", hist="villain-arc")
    assert (r.translatable, r.language, r.story_id, r.warning) == (False, None, "villain-arc", None)


def test_row5_lang_and_no():
    r = resolve_attributes(lang="es", no=True)
    assert (r.translatable, r.language, r.story_id, r.warning) == (True, "es", None, None)


def test_row6_nolang_and_no():
    r = resolve_attributes(lang="nolang", no=True)
    assert (r.translatable, r.language, r.story_id, r.warning) == (False, None, None, None)


def test_row7_conflict_lang():
    r = resolve_attributes(lang="es", hist="villain-arc", no=True)
    assert r.translatable is True
    assert r.language == "es"
    assert r.story_id is None
    assert r.warning is not None


def test_row8_conflict_nolang():
    r = resolve_attributes(lang="nolang", hist="villain-arc", no=True)
    assert r.translatable is False
    assert r.story_id is None
    assert r.warning is not None


def test_row9_nothing():
    r = resolve_attributes()
    assert (r.translatable, r.language, r.story_id, r.warning) == (False, None, None, None)


def test_row10_no_only():
    r = resolve_attributes(no=True)
    assert (r.translatable, r.language, r.story_id, r.warning) == (False, None, None, None)


def test_row11_hist_inherits_language():
    r = resolve_attributes(hist="villain-arc", inherited_lang="es")
    assert (r.translatable, r.language, r.story_id, r.warning) == (True, "es", "villain-arc", None)


def test_row11_hist_without_inheritance_hard_fails():
    with pytest.raises(ValidationError):
        resolve_attributes(hist="villain-arc")


def test_row12_conflict_without_lang():
    r = resolve_attributes(hist="villain-arc", no=True, inherited_lang="es")
    assert (r.translatable, r.language, r.story_id) == (False, None, None)
    assert r.warning is not None
