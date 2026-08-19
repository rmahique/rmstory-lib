import pytest

from rmstory.engines import get_engine
from rmstory.engines.ollama import OllamaEngine
from rmstory.exceptions import TranslationError


def test_translate_with_injected_http_post():
    calls = []

    def fake_http_post(url, payload):
        calls.append((url, payload))
        return {"message": {"role": "assistant", "content": "Hola, viajero."}}

    engine = OllamaEngine(base_url="http://example.test", model="llama3.1", http_post=fake_http_post)

    result = engine.translate("Hello, traveler.", "en", "es")

    assert result == "Hola, viajero."
    url, payload = calls[0]
    assert url == "http://example.test/api/chat"
    assert payload["model"] == "llama3.1"
    assert payload["stream"] is False
    assert payload["messages"] == [{"role": "user", "content": payload["messages"][0]["content"]}]
    assert "Hello, traveler." in payload["messages"][0]["content"]


def test_default_url_is_localhost(monkeypatch):
    monkeypatch.delenv("RMSTORY_OLLAMA_URL", raising=False)
    engine = OllamaEngine(model="llama3.1", http_post=lambda url, payload: {"message": {"content": "x"}})
    assert engine._base_url == "http://localhost:11434"


def test_trailing_slash_stripped():
    engine = OllamaEngine(
        base_url="http://example.test/",
        model="llama3.1",
        http_post=lambda url, payload: {"message": {"content": "x"}},
    )
    assert engine._base_url == "http://example.test"


def test_model_env_var_fallback(monkeypatch):
    monkeypatch.setenv("RMSTORY_OLLAMA_MODEL", "qwen2.5")
    engine = OllamaEngine(http_post=lambda url, payload: {"message": {"content": "x"}})
    assert engine._model == "qwen2.5"


def test_missing_model_raises_value_error(monkeypatch):
    monkeypatch.delenv("RMSTORY_OLLAMA_MODEL", raising=False)
    with pytest.raises(ValueError):
        OllamaEngine(http_post=lambda url, payload: {"message": {"content": "x"}})


def test_empty_response_raises_translation_error():
    engine = OllamaEngine(model="llama3.1", http_post=lambda url, payload: {"message": {"content": "  "}})
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_malformed_response_raises_translation_error():
    engine = OllamaEngine(model="llama3.1", http_post=lambda url, payload: {"error": "no such model"})
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_underlying_error_wrapped():
    def fake_http_post(url, payload):
        raise OSError("connection refused")

    engine = OllamaEngine(model="llama3.1", http_post=fake_http_post)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_get_engine_uses_registry():
    engine = get_engine(
        "ollama",
        model="llama3.1",
        http_post=lambda url, payload: {"message": {"content": "Hola"}},
    )
    assert engine.translate("Hello", "en", "es") == "Hola"


def test_supports_generation():
    assert OllamaEngine.SUPPORTS_GENERATION is True


def test_generate_sends_raw_prompt():
    calls = []

    def fake_http_post(url, payload):
        calls.append(payload)
        return {"message": {"content": "Once upon a time..."}}

    engine = OllamaEngine(model="llama3.1", http_post=fake_http_post)
    result = engine.generate("write a short story")

    assert result == "Once upon a time..."
    assert calls[0]["messages"] == [{"role": "user", "content": "write a short story"}]


def test_generate_empty_response_raises_translation_error():
    engine = OllamaEngine(model="llama3.1", http_post=lambda url, payload: {"message": {"content": "  "}})
    with pytest.raises(TranslationError):
        engine.generate("write a story")
