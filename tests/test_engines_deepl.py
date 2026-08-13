import sys

import pytest

from rmstory.engines import get_engine
from rmstory.engines.deepl import DeepLEngine
from rmstory.exceptions import TranslationError


class _FakeResult:
    def __init__(self, text):
        self.text = text


class _FakeTranslator:
    def __init__(self, response_text="Hola"):
        self.response_text = response_text
        self.calls = []

    def translate_text(self, text, source_lang, target_lang):
        self.calls.append((text, source_lang, target_lang))
        return _FakeResult(self.response_text)


def test_translate_uppercases_lang_codes_and_returns_text():
    client = _FakeTranslator(response_text="Hola, viajero.")
    engine = DeepLEngine(client=client)

    result = engine.translate("Hello, traveler.", "en", "es")

    assert result == "Hola, viajero."
    text, source_lang, target_lang = client.calls[0]
    assert (text, source_lang, target_lang) == ("Hello, traveler.", "EN", "ES")


def test_translate_strips_whitespace():
    client = _FakeTranslator(response_text="  Hola  \n")
    engine = DeepLEngine(client=client)
    assert engine.translate("Hello", "en", "es") == "Hola"


def test_empty_response_raises_translation_error():
    client = _FakeTranslator(response_text="")
    engine = DeepLEngine(client=client)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_underlying_error_wrapped_as_translation_error():
    class _BrokenTranslator:
        def translate_text(self, text, source_lang, target_lang):
            raise RuntimeError("quota exceeded")

    engine = DeepLEngine(client=_BrokenTranslator())
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_get_engine_uses_registry():
    client = _FakeTranslator(response_text="Hola")
    assert get_engine("deepl", client=client).translate("Hello", "en", "es") == "Hola"


def test_missing_credentials_raises_value_error(monkeypatch):
    monkeypatch.delenv("DEEPL_AUTH_KEY", raising=False)
    with pytest.raises(ValueError):
        DeepLEngine()


def test_auth_key_from_env(monkeypatch):
    # Without the real `deepl` package installed this still exercises the
    # credential check; the ImportError below confirms it got that far
    # rather than failing on the missing auth key.
    monkeypatch.setenv("DEEPL_AUTH_KEY", "fake-key")
    monkeypatch.setitem(sys.modules, "deepl", None)
    with pytest.raises(ImportError):
        DeepLEngine()


def test_missing_sdk_raises_import_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "deepl", None)
    with pytest.raises(ImportError):
        DeepLEngine(auth_key="fake-key")
