from typing import ClassVar

import pytest

from rmstory import engines, generation
from rmstory.exceptions import TranslationError
from rmstory.run import ResolvedSpan


def _span(span_id, content, translatable=True, language="en"):
    return ResolvedSpan(
        path="doc.md",
        line=1,
        id=span_id,
        content=content,
        translatable=translatable,
        language=language,
        story_id=None,
        warning=None,
        tag_start=0,
        tag_text='<span lang="{}" id="{}">'.format(language, span_id),
        content_start=0,
        content_end=len(content),
        tag_end=len(content),
        end_tag_text="</span>",
        parent_id=None,
        parent_tag_start=None,
    )


class _FakeLLM:
    """A no-network engine registered in tests via engines._ENGINES for
    generation.py's tests to exercise without real credentials."""

    SUPPORTS_GENERATION = True
    calls: ClassVar[list] = []

    def __init__(self, response=None):
        self._response = response

    def generate(self, prompt):
        _FakeLLM.calls.append(prompt)
        return self._response


class _FakeNonGenerating:
    SUPPORTS_GENERATION = False

    def translate(self, text, from_lang, to_lang):
        return text


def test_generation_capable_engines_matches_llm_backed_registry():
    assert generation.generation_capable_engines() == {
        "gemini",
        "claude-code",
        "ollama",
        "deepseek",
        "mistral",
        "qwen",
        "kimi",
    }


def test_generate_with_engine_returns_engine_output():
    engine = _FakeLLM(response="a new tale")
    assert generation.generate_with_engine(engine, "write something") == "a new tale"


def test_generate_with_engine_rejects_non_generating_engine():
    with pytest.raises(ValueError, match="doesn't support story generation"):
        generation.generate_with_engine(_FakeNonGenerating(), "write something")


def test_generate_text_uses_registry(monkeypatch):
    monkeypatch.setitem(engines._ENGINES, "fake-llm", lambda **kw: _FakeLLM(response="hi"))
    assert generation.generate_text("write something", engine="fake-llm") == "hi"


def test_generate_text_rejects_non_generating_engine(monkeypatch):
    monkeypatch.setitem(engines._ENGINES, "fake-translate-only", lambda **kw: _FakeNonGenerating())
    with pytest.raises(ValueError):
        generation.generate_text("write something", engine="fake-translate-only")


def test_rewrite_spans_content_no_targets_skips_engine_call():
    _FakeLLM.calls = []
    engine = _FakeLLM()
    spans = [_span("ch1.title", "The Arrival", translatable=False)]

    result = generation.rewrite_spans_content(spans, engine)

    assert result == {}
    assert _FakeLLM.calls == []


def test_rewrite_spans_content_parses_response_and_ignores_non_translatable():
    spans = [
        _span("ch1.greeting", "Hello, traveler."),
        _span("ch1.reveal", "The mayor was the villain."),
        _span("ch1.title", "Chapter One", translatable=False),
    ]
    response = (
        "===[ch1.greeting]===\n"
        "Welcome, wanderer.\n\n"
        "===[ch1.reveal]===\n"
        "The baker was the spy all along."
    )
    engine = _FakeLLM(response=response)

    result = generation.rewrite_spans_content(spans, engine)

    assert result == {
        "ch1.greeting": ("Welcome, wanderer.", "en"),
        "ch1.reveal": ("The baker was the spy all along.", "en"),
    }
    assert "ch1.title" not in result


def test_rewrite_spans_content_includes_theme_in_prompt():
    _FakeLLM.calls = []
    spans = [_span("ch1.greeting", "Hello, traveler.")]
    engine = _FakeLLM(response="===[ch1.greeting]===\nHi there.")

    generation.rewrite_spans_content(spans, engine, theme="a haunted lighthouse")

    assert "a haunted lighthouse" in _FakeLLM.calls[0]


def test_rewrite_spans_content_missing_part_raises_translation_error():
    spans = [_span("ch1.greeting", "Hello, traveler."), _span("ch1.reveal", "The mayor.")]
    engine = _FakeLLM(response="===[ch1.greeting]===\nHi there.")

    with pytest.raises(TranslationError, match="ch1.reveal"):
        generation.rewrite_spans_content(spans, engine)


def test_rewrite_spans_content_malformed_response_raises_translation_error():
    spans = [_span("ch1.greeting", "Hello, traveler.")]
    engine = _FakeLLM(response="just some prose, no delimiters at all")

    with pytest.raises(TranslationError):
        generation.rewrite_spans_content(spans, engine)


def test_rewrite_spans_content_missing_placeholder_raises_translation_error():
    content = 'The mayor -- <span id="ch1.hero-name"/>\'s uncle -- was the villain.'
    spans = [_span("ch1.reveal", content)]
    engine = _FakeLLM(response="===[ch1.reveal]===\nThe baker was the spy, no name mentioned.")

    with pytest.raises(TranslationError, match="ch1.hero-name"):
        generation.rewrite_spans_content(spans, engine)


def test_rewrite_spans_content_preserved_placeholder_passes():
    content = 'The mayor -- <span id="ch1.hero-name"/>\'s uncle -- was the villain.'
    spans = [_span("ch1.reveal", content)]
    new_text = 'The baker -- <span id="ch1.hero-name"/>\'s neighbor -- was the spy.'
    engine = _FakeLLM(response="===[ch1.reveal]===\n" + new_text)

    result = generation.rewrite_spans_content(spans, engine)

    assert result == {"ch1.reveal": (new_text, "en")}


def test_rewrite_spans_content_rejects_non_generating_engine():
    spans = [_span("ch1.greeting", "Hello, traveler.")]
    with pytest.raises(ValueError):
        generation.rewrite_spans_content(spans, _FakeNonGenerating())


def test_generate_new_story_wraps_prompt(monkeypatch):
    engine = _FakeLLM(response='<span lang="en" id="ch1.a">Once upon a time.</span>')

    result = generation.generate_new_story("a lighthouse keeper", engine, lang="en")

    assert result == '<span lang="en" id="ch1.a">Once upon a time.</span>'
    prompt = _FakeLLM.calls[-1]
    assert "a lighthouse keeper" in prompt
    assert 'lang="en"' in prompt


def test_generate_new_story_rejects_non_generating_engine():
    with pytest.raises(ValueError):
        generation.generate_new_story("a lighthouse keeper", _FakeNonGenerating())
