import pytest

from rmstory.engines import get_engine
from rmstory.engines.libretranslate import LibreTranslateEngine
from rmstory.exceptions import TranslationError


def test_translate_with_injected_http_post():
    calls = []

    def fake_http_post(url, payload):
        calls.append((url, payload))
        return {"translatedText": "Hola, viajero."}

    engine = LibreTranslateEngine(base_url="http://example.test", http_post=fake_http_post)

    result = engine.translate("Hello, traveler.", "en", "es")

    assert result == "Hola, viajero."
    url, payload = calls[0]
    assert url == "http://example.test/translate"
    assert payload == {"q": "Hello, traveler.", "source": "en", "target": "es", "format": "text"}
    assert "api_key" not in payload


def test_default_url_is_localhost(monkeypatch):
    monkeypatch.delenv("LIBRETRANSLATE_URL", raising=False)
    engine = LibreTranslateEngine(http_post=lambda url, payload: {"translatedText": "x"})
    assert engine._base_url == "http://localhost:5000"


def test_trailing_slash_stripped():
    engine = LibreTranslateEngine(
        base_url="http://example.test/", http_post=lambda url, payload: {"translatedText": "x"}
    )
    assert engine._base_url == "http://example.test"


def test_api_key_included_when_given():
    calls = []

    def fake_http_post(url, payload):
        calls.append(payload)
        return {"translatedText": "Hola"}

    engine = LibreTranslateEngine(
        base_url="http://example.test", api_key="secret", http_post=fake_http_post
    )
    engine.translate("Hello", "en", "es")

    assert calls[0]["api_key"] == "secret"


def test_no_credential_required():
    # LibreTranslate self-hosted with API_KEYS disabled needs nothing at all.
    engine = LibreTranslateEngine(
        base_url="http://example.test", http_post=lambda url, payload: {"translatedText": "Hola"}
    )
    assert engine.translate("Hello", "en", "es") == "Hola"


def test_empty_response_raises_translation_error():
    engine = LibreTranslateEngine(
        base_url="http://example.test",
        http_post=lambda url, payload: {"translatedText": ""},
    )
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_malformed_response_raises_translation_error():
    engine = LibreTranslateEngine(
        base_url="http://example.test", http_post=lambda url, payload: {"error": "bad request"}
    )
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_underlying_error_wrapped():
    def fake_http_post(url, payload):
        raise OSError("connection refused")

    engine = LibreTranslateEngine(base_url="http://example.test", http_post=fake_http_post)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_get_engine_uses_registry():
    engine = get_engine(
        "libretranslate",
        base_url="http://example.test",
        http_post=lambda url, payload: {"translatedText": "Hola"},
    )
    assert engine.translate("Hello", "en", "es") == "Hola"
