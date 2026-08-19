import pytest

from rmstory.engines import get_engine
from rmstory.engines.microsoft import MicrosoftTranslatorEngine
from rmstory.exceptions import TranslationError


def test_translate_with_injected_http_post():
    calls = []

    def fake_http_post(url, headers, payload):
        calls.append((url, headers, payload))
        return [{"translations": [{"text": "Hola, viajero.", "to": "es"}]}]

    engine = MicrosoftTranslatorEngine(api_key="fake-key", http_post=fake_http_post)

    result = engine.translate("Hello, traveler.", "en", "es")

    assert result == "Hola, viajero."
    url, headers, payload = calls[0]
    assert "from=en" in url and "to=es" in url
    assert headers["Ocp-Apim-Subscription-Key"] == "fake-key"
    assert "Ocp-Apim-Subscription-Region" not in headers
    assert payload == [{"Text": "Hello, traveler."}]


def test_region_header_included_when_given():
    calls = []

    def fake_http_post(url, headers, payload):
        calls.append(headers)
        return [{"translations": [{"text": "Hola"}]}]

    engine = MicrosoftTranslatorEngine(
        api_key="fake-key", region="westeurope", http_post=fake_http_post
    )
    engine.translate("Hello", "en", "es")

    assert calls[0]["Ocp-Apim-Subscription-Region"] == "westeurope"


def test_empty_response_raises_translation_error():
    def fake_http_post(url, headers, payload):
        return [{"translations": [{"text": ""}]}]

    engine = MicrosoftTranslatorEngine(api_key="fake-key", http_post=fake_http_post)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_malformed_response_raises_translation_error():
    def fake_http_post(url, headers, payload):
        return {"error": {"message": "invalid key"}}

    engine = MicrosoftTranslatorEngine(api_key="fake-key", http_post=fake_http_post)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_underlying_error_wrapped():
    def fake_http_post(url, headers, payload):
        raise OSError("network down")

    engine = MicrosoftTranslatorEngine(api_key="fake-key", http_post=fake_http_post)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_missing_credentials_raises_value_error(monkeypatch):
    monkeypatch.delenv("AZURE_TRANSLATOR_KEY", raising=False)
    with pytest.raises(ValueError):
        MicrosoftTranslatorEngine()


def test_api_key_from_env(monkeypatch):
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "env-key")

    def fake_http_post(url, headers, payload):
        assert headers["Ocp-Apim-Subscription-Key"] == "env-key"
        return [{"translations": [{"text": "Hola"}]}]

    engine = MicrosoftTranslatorEngine(http_post=fake_http_post)
    assert engine.translate("Hello", "en", "es") == "Hola"


def test_get_engine_uses_registry():
    def fake_http_post(url, headers, payload):
        return [{"translations": [{"text": "Hola"}]}]

    engine = get_engine("microsoft-translator", api_key="fake-key", http_post=fake_http_post)
    assert engine.translate("Hello", "en", "es") == "Hola"


def test_does_not_support_generation():
    assert MicrosoftTranslatorEngine.SUPPORTS_GENERATION is False
