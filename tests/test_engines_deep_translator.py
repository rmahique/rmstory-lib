import sys

import pytest

from rmstory.engines import get_engine, translate_text
from rmstory.engines.deep_translator import DeepTranslatorEngine
from rmstory.exceptions import TranslationError


class _FakeTranslator:
    def __init__(self, response_text="Hola"):
        self.response_text = response_text
        self.calls = []

    def translate(self, text):
        self.calls.append(text)
        return self.response_text


def _factory_returning(translator, record=None):
    def factory(provider, source, target, api_key):
        if record is not None:
            record.append((provider, source, target, api_key))
        return translator

    return factory


def test_translate_returns_text_and_passes_langs():
    fake = _FakeTranslator(response_text="Hola, viajero.")
    record = []
    engine = DeepTranslatorEngine(translator_factory=_factory_returning(fake, record))

    result = engine.translate("Hello, traveler.", "en", "es")

    assert result == "Hola, viajero."
    assert fake.calls == ["Hello, traveler."]
    provider, source, target, _api_key = record[0]
    assert (provider, source, target) == ("google", "en", "es")


def test_chinese_tag_mapped_to_regional_code():
    record = []
    engine = DeepTranslatorEngine(translator_factory=_factory_returning(_FakeTranslator(), record))
    engine.translate("Hello", "en", "zh")
    assert record[0][2] == "zh-CN"


def test_empty_from_lang_becomes_auto():
    record = []
    engine = DeepTranslatorEngine(translator_factory=_factory_returning(_FakeTranslator(), record))
    engine.translate("Hello", "", "es")
    assert record[0][1] == "auto"


def test_translate_strips_whitespace():
    engine = DeepTranslatorEngine(
        translator_factory=_factory_returning(_FakeTranslator("  Hola  \n"))
    )
    assert engine.translate("Hello", "en", "es") == "Hola"


def test_empty_response_raises_translation_error():
    engine = DeepTranslatorEngine(translator_factory=_factory_returning(_FakeTranslator("")))
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_underlying_error_wrapped_as_translation_error():
    class _Broken:
        def translate(self, text):
            raise RuntimeError("boom")

    engine = DeepTranslatorEngine(translator_factory=_factory_returning(_Broken()))
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_rate_limit_is_retried_then_succeeds(monkeypatch):
    # deep-translator's TooManyRequests carries no HTTP status; the engine
    # tags it so call_with_retry treats it as transient. This exercises that
    # wiring end to end (not call_with_retry in isolation).
    monkeypatch.setattr("rmstory.engines.base.time.sleep", lambda seconds: None)

    _TooManyRequests = type("TooManyRequests", (Exception,), {})

    class _Flaky:
        def __init__(self):
            self.calls = 0

        def translate(self, text):
            self.calls += 1
            if self.calls == 1:
                raise _TooManyRequests("slow down")
            return "Hola"

    flaky = _Flaky()
    engine = DeepTranslatorEngine(translator_factory=_factory_returning(flaky))

    assert engine.translate("Hello", "en", "es") == "Hola"
    assert flaky.calls == 2


def test_unknown_provider_raises_value_error():
    with pytest.raises(ValueError):
        DeepTranslatorEngine(provider="bing")


def test_deepl_provider_requires_credentials(monkeypatch):
    monkeypatch.delenv("DEEPL_AUTH_KEY", raising=False)
    with pytest.raises(ValueError):
        DeepTranslatorEngine(provider="deepl")


def test_deepl_provider_key_from_env(monkeypatch):
    monkeypatch.setenv("DEEPL_AUTH_KEY", "fake-key")
    record = []
    engine = DeepTranslatorEngine(
        provider="deepl",
        translator_factory=_factory_returning(_FakeTranslator("Hallo"), record),
    )
    assert engine.translate("Hello", "en", "de") == "Hallo"
    assert record[0][0] == "deepl"
    assert record[0][3] == "fake-key"


def test_get_engine_and_translate_text_use_registry():
    factory = _factory_returning(_FakeTranslator(response_text="Hola"))
    assert (
        get_engine("deep-translator", translator_factory=factory).translate("Hello", "en", "es")
        == "Hola"
    )
    assert (
        translate_text("Hello", "en", "es", engine="deep-translator", translator_factory=factory)
        == "Hola"
    )


def test_missing_package_raises_import_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "deep_translator", None)
    with pytest.raises(ImportError):
        DeepTranslatorEngine()


def test_does_not_support_generation():
    assert DeepTranslatorEngine.SUPPORTS_GENERATION is False
