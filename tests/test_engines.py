import sys

import pytest

from rmstory.engines import get_engine, translate_text
from rmstory.engines.gemini import GeminiEngine
from rmstory.exceptions import TranslationError


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, response_text="Hola"):
        self.response_text = response_text
        self.calls = []

    def generate_content(self, model, contents):
        self.calls.append((model, contents))
        return _FakeResponse(self.response_text)


class _FakeClient:
    def __init__(self, response_text="Hola"):
        self.models = _FakeModels(response_text)


def test_translate_with_injected_client():
    client = _FakeClient(response_text="Hola, viajero.")
    engine = GeminiEngine(client=client)

    result = engine.translate("Hello, traveler.", "en", "es")

    assert result == "Hola, viajero."
    _model, prompt = client.models.calls[0]
    assert "Hello, traveler." in prompt
    assert "en" in prompt and "es" in prompt


def test_translate_strips_whitespace():
    client = _FakeClient(response_text="  Hola  \n")
    engine = GeminiEngine(client=client)
    assert engine.translate("Hello", "en", "es") == "Hola"


def test_empty_response_raises_translation_error():
    client = _FakeClient(response_text="")
    engine = GeminiEngine(client=client)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_underlying_error_wrapped_as_translation_error():
    class _BrokenModels:
        def generate_content(self, model, contents):
            raise RuntimeError("network down")

    class _BrokenClient:
        models = _BrokenModels()

    engine = GeminiEngine(client=_BrokenClient())
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_get_engine_and_translate_text_use_registry():
    client = _FakeClient(response_text="Hola")
    assert get_engine("gemini", client=client).translate("Hello", "en", "es") == "Hola"
    assert translate_text("Hello", "en", "es", engine="gemini", client=client) == "Hola"


def test_unknown_engine_raises():
    with pytest.raises(ValueError):
        get_engine("bing-translate")


def test_missing_sdk_raises_import_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "google.genai", None)
    with pytest.raises(ImportError):
        GeminiEngine(api_key="fake-key")


# The credential-selection logic (free API-key tier vs. account-based
# Vertex AI) is exercised directly against _resolve_client_kwargs rather
# than through __init__, so these don't need the real SDK installed or any
# import-machinery mocking -- see gemini.py's docstring on why it's split
# out.


def test_free_tier_uses_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)

    kwargs = GeminiEngine._resolve_client_kwargs("ai-studio-key", None, None, None)

    assert kwargs == {"api_key": "ai-studio-key"}


def test_free_tier_falls_back_to_env_var(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)

    kwargs = GeminiEngine._resolve_client_kwargs(None, None, None, None)

    assert kwargs == {"api_key": "from-env"}


def test_account_based_uses_vertex_project():
    kwargs = GeminiEngine._resolve_client_kwargs(
        None, "my-gcp-project", "europe-west1", True
    )

    assert kwargs == {"vertexai": True, "project": "my-gcp-project", "location": "europe-west1"}


def test_project_alone_implies_vertex_mode(monkeypatch):
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)

    kwargs = GeminiEngine._resolve_client_kwargs(None, "my-gcp-project", None, None)

    assert kwargs == {"vertexai": True, "project": "my-gcp-project", "location": "us-central1"}


def test_no_credentials_raises_value_error(monkeypatch):
    for var in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_GENAI_USE_VERTEXAI",
    ):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(ValueError):
        GeminiEngine._resolve_client_kwargs(None, None, None, None)


def test_vertex_mode_without_project_raises_value_error():
    with pytest.raises(ValueError):
        GeminiEngine._resolve_client_kwargs(None, None, None, True)
