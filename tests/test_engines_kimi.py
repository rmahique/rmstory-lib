import pytest

from rmstory.engines import get_engine
from rmstory.engines.kimi import KimiEngine
from rmstory.exceptions import TranslationError


def _response(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def test_translate_with_injected_http_post():
    calls = []

    def fake_http_post(url, payload):
        calls.append((url, payload))
        return _response("Hola, viajero.")

    engine = KimiEngine(base_url="http://example.test", http_post=fake_http_post)

    result = engine.translate("Hello, traveler.", "en", "es")

    assert result == "Hola, viajero."
    url, payload = calls[0]
    assert url == "http://example.test/chat/completions"
    assert payload["model"] == "kimi-latest"
    assert "Hello, traveler." in payload["messages"][0]["content"]


def test_translate_preserves_nested_span_placeholder_in_prompt():
    calls = []

    def fake_http_post(url, payload):
        calls.append(payload)
        return _response('<span id="a.1"/> の下')

    engine = KimiEngine(http_post=fake_http_post)
    text = 'Under the <span id="a.1"/> tab.'

    result = engine.translate(text, "en", "ja")

    assert result == '<span id="a.1"/> の下'
    sent_prompt = calls[0]["messages"][0]["content"]
    assert text in sent_prompt
    assert "placeholder" in sent_prompt


def test_default_url_and_model(monkeypatch):
    monkeypatch.delenv("RMSTORY_KIMI_URL", raising=False)
    monkeypatch.delenv("RMSTORY_KIMI_MODEL", raising=False)
    engine = KimiEngine(http_post=lambda url, payload: _response("x"))
    assert engine._base_url == "https://api.moonshot.ai/v1"
    assert engine._model == "kimi-latest"


def test_trailing_slash_stripped():
    engine = KimiEngine(base_url="http://example.test/", http_post=lambda url, payload: _response("x"))
    assert engine._base_url == "http://example.test"


def test_model_env_var_fallback(monkeypatch):
    monkeypatch.setenv("RMSTORY_KIMI_MODEL", "kimi-k2-0711-preview")
    engine = KimiEngine(http_post=lambda url, payload: _response("x"))
    assert engine._model == "kimi-k2-0711-preview"


def test_url_env_var_switches_region(monkeypatch):
    monkeypatch.setenv("RMSTORY_KIMI_URL", "https://api.moonshot.cn/v1")
    engine = KimiEngine(http_post=lambda url, payload: _response("x"))
    assert engine._base_url == "https://api.moonshot.cn/v1"


def test_missing_credentials_raises_value_error(monkeypatch):
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    with pytest.raises(ValueError):
        KimiEngine()


def test_api_key_from_env_threaded_into_default_http_post(monkeypatch):
    monkeypatch.setenv("MOONSHOT_API_KEY", "secret-key")
    engine = KimiEngine()

    calls = []
    monkeypatch.setattr(
        "rmstory.engines.kimi._openai_chat.default_http_post",
        lambda url, payload, api_key: calls.append((url, payload, api_key)) or _response("Hola"),
    )
    assert engine.translate("Hello", "en", "es") == "Hola"
    assert calls[0][2] == "secret-key"


def test_empty_response_raises_translation_error():
    engine = KimiEngine(http_post=lambda url, payload: _response("  "))
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_malformed_response_raises_translation_error():
    engine = KimiEngine(http_post=lambda url, payload: {"error": "bad request"})
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_underlying_error_wrapped():
    def fake_http_post(url, payload):
        raise OSError("connection refused")

    engine = KimiEngine(http_post=fake_http_post)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_get_engine_uses_registry():
    engine = get_engine("kimi", http_post=lambda url, payload: _response("Hola"))
    assert engine.translate("Hello", "en", "es") == "Hola"


def test_supports_generation():
    assert KimiEngine.SUPPORTS_GENERATION is True


def test_generate_sends_raw_prompt():
    calls = []

    def fake_http_post(url, payload):
        calls.append(payload)
        return _response("Once upon a time...")

    engine = KimiEngine(http_post=fake_http_post)
    result = engine.generate("write a short story")

    assert result == "Once upon a time..."
    assert calls[0]["messages"] == [{"role": "user", "content": "write a short story"}]


def test_generate_empty_response_raises_translation_error():
    engine = KimiEngine(http_post=lambda url, payload: _response("  "))
    with pytest.raises(TranslationError):
        engine.generate("write a story")
