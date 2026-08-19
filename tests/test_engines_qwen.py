import pytest

from rmstory.engines import get_engine
from rmstory.engines.qwen import QwenEngine
from rmstory.exceptions import TranslationError


def _response(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def test_translate_with_injected_http_post():
    calls = []

    def fake_http_post(url, payload):
        calls.append((url, payload))
        return _response("Hola, viajero.")

    engine = QwenEngine(base_url="http://example.test", http_post=fake_http_post)

    result = engine.translate("Hello, traveler.", "en", "es")

    assert result == "Hola, viajero."
    url, payload = calls[0]
    assert url == "http://example.test/chat/completions"
    assert payload["model"] == "qwen-plus"
    assert "Hello, traveler." in payload["messages"][0]["content"]


def test_default_url_and_model(monkeypatch):
    monkeypatch.delenv("RMSTORY_QWEN_URL", raising=False)
    monkeypatch.delenv("RMSTORY_QWEN_MODEL", raising=False)
    engine = QwenEngine(http_post=lambda url, payload: _response("x"))
    assert engine._base_url == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    assert engine._model == "qwen-plus"


def test_trailing_slash_stripped():
    engine = QwenEngine(base_url="http://example.test/", http_post=lambda url, payload: _response("x"))
    assert engine._base_url == "http://example.test"


def test_model_env_var_fallback(monkeypatch):
    monkeypatch.setenv("RMSTORY_QWEN_MODEL", "qwen-turbo")
    engine = QwenEngine(http_post=lambda url, payload: _response("x"))
    assert engine._model == "qwen-turbo"


def test_url_env_var_switches_region(monkeypatch):
    monkeypatch.setenv("RMSTORY_QWEN_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    engine = QwenEngine(http_post=lambda url, payload: _response("x"))
    assert engine._base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_missing_credentials_raises_value_error(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    with pytest.raises(ValueError):
        QwenEngine()


def test_api_key_from_env_threaded_into_default_http_post(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "secret-key")
    engine = QwenEngine()

    calls = []
    monkeypatch.setattr(
        "rmstory.engines.qwen._openai_chat.default_http_post",
        lambda url, payload, api_key: calls.append((url, payload, api_key)) or _response("Hola"),
    )
    assert engine.translate("Hello", "en", "es") == "Hola"
    assert calls[0][2] == "secret-key"


def test_empty_response_raises_translation_error():
    engine = QwenEngine(http_post=lambda url, payload: _response("  "))
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_malformed_response_raises_translation_error():
    engine = QwenEngine(http_post=lambda url, payload: {"error": "bad request"})
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_underlying_error_wrapped():
    def fake_http_post(url, payload):
        raise OSError("connection refused")

    engine = QwenEngine(http_post=fake_http_post)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_get_engine_uses_registry():
    engine = get_engine("qwen", http_post=lambda url, payload: _response("Hola"))
    assert engine.translate("Hello", "en", "es") == "Hola"


def test_supports_generation():
    assert QwenEngine.SUPPORTS_GENERATION is True


def test_generate_sends_raw_prompt():
    calls = []

    def fake_http_post(url, payload):
        calls.append(payload)
        return _response("Once upon a time...")

    engine = QwenEngine(http_post=fake_http_post)
    result = engine.generate("write a short story")

    assert result == "Once upon a time..."
    assert calls[0]["messages"] == [{"role": "user", "content": "write a short story"}]


def test_generate_empty_response_raises_translation_error():
    engine = QwenEngine(http_post=lambda url, payload: _response("  "))
    with pytest.raises(TranslationError):
        engine.generate("write a story")
