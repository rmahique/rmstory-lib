import sys
import types

import pytest

from rmstory.engines import get_engine
from rmstory.engines.google_translate import GoogleTranslateEngine
from rmstory.exceptions import TranslationError

# --- v3 / account-based mode (SDK client injected) -------------------------


class _FakeTranslation:
    def __init__(self, translated_text):
        self.translated_text = translated_text


class _FakeV3Response:
    def __init__(self, translated_text):
        self.translations = [_FakeTranslation(translated_text)] if translated_text is not None else []


class _FakeV3Client:
    def __init__(self, response_text="Hola"):
        self.response_text = response_text
        self.calls = []

    def translate_text(self, request):
        self.calls.append(request)
        return _FakeV3Response(self.response_text)


def test_v3_translate_with_injected_client():
    client = _FakeV3Client(response_text="Hola, viajero.")
    engine = GoogleTranslateEngine(project="my-project", client=client)

    result = engine.translate("Hello, traveler.", "en", "es")

    assert result == "Hola, viajero."
    request = client.calls[0]
    assert request["parent"] == "projects/my-project/locations/global"
    assert request["contents"] == ["Hello, traveler."]
    assert request["source_language_code"] == "en"
    assert request["target_language_code"] == "es"


def test_v3_custom_location():
    client = _FakeV3Client()
    engine = GoogleTranslateEngine(project="my-project", location="europe-west1", client=client)
    engine.translate("Hello", "en", "es")
    assert client.calls[0]["parent"] == "projects/my-project/locations/europe-west1"


def test_v3_empty_response_raises_translation_error():
    client = _FakeV3Client(response_text=None)
    engine = GoogleTranslateEngine(project="my-project", client=client)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_v3_underlying_error_wrapped():
    class _BrokenClient:
        def translate_text(self, request):
            raise RuntimeError("permission denied")

    engine = GoogleTranslateEngine(project="my-project", client=_BrokenClient())
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


# --- v2 / free-ish API-key mode (HTTP call injected) ------------------------


def test_v2_translate_with_injected_http_post():
    calls = []

    def fake_http_post(url, payload):
        calls.append((url, payload))
        return {"data": {"translations": [{"translatedText": "Hola, viajero."}]}}

    engine = GoogleTranslateEngine(api_key="ai-key", http_post=fake_http_post)

    result = engine.translate("Hello, traveler.", "en", "es")

    assert result == "Hola, viajero."
    url, payload = calls[0]
    assert "key=ai-key" in url
    assert payload == {"q": "Hello, traveler.", "source": "en", "target": "es", "format": "text"}


def test_v2_empty_response_raises_translation_error():
    def fake_http_post(url, payload):
        return {"data": {"translations": [{"translatedText": ""}]}}

    engine = GoogleTranslateEngine(api_key="ai-key", http_post=fake_http_post)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_v2_malformed_response_raises_translation_error():
    def fake_http_post(url, payload):
        return {"error": "quota exceeded"}

    engine = GoogleTranslateEngine(api_key="ai-key", http_post=fake_http_post)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_v2_underlying_error_wrapped():
    def fake_http_post(url, payload):
        raise OSError("network down")

    engine = GoogleTranslateEngine(api_key="ai-key", http_post=fake_http_post)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


# --- mode selection ----------------------------------------------------------


def test_api_key_selects_v2_without_needing_sdk(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    engine = GoogleTranslateEngine(api_key="ai-key", http_post=lambda url, payload: {})
    assert engine._mode == "v2"


def test_project_selects_v3_and_requires_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "google.cloud.translate", None)
    with pytest.raises(ImportError):
        GoogleTranslateEngine(project="my-project")


def test_project_env_var_selects_v3(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
    api_key, project = GoogleTranslateEngine._resolve_credentials(None, None)
    assert (api_key, project) == (None, "env-project")


def test_api_key_env_var_fallback(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.setenv("GOOGLE_TRANSLATE_API_KEY", "env-key")
    api_key, project = GoogleTranslateEngine._resolve_credentials(None, None)
    assert (api_key, project) == ("env-key", None)


def test_no_credentials_raises_value_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_TRANSLATE_API_KEY", raising=False)
    with pytest.raises(ValueError):
        GoogleTranslateEngine._resolve_credentials(None, None)


def test_api_key_wins_over_project_when_both_present(monkeypatch):
    # GOOGLE_CLOUD_PROJECT is often already set for unrelated reasons (gcloud
    # config, the gemini engine's own Vertex mode); it must not silently
    # force v3's ADC requirement when a working API key is also available.
    engine = GoogleTranslateEngine(
        api_key="ai-key", project="my-project", http_post=lambda url, payload: {}
    )
    assert engine._mode == "v2"


def test_client_forces_v3_even_with_api_key_present():
    client = _FakeV3Client(response_text="Hola")
    engine = GoogleTranslateEngine(api_key="ai-key", project="my-project", client=client)
    assert engine._mode == "v3"
    assert engine.translate("Hello", "en", "es") == "Hola"


def test_v3_auth_failure_at_construction_raises_clean_value_error(monkeypatch):
    # TranslationServiceClient() validates Application Default Credentials
    # eagerly at construction time (unlike the gemini engine's lazy-auth
    # SDK) -- a raw google.auth.exceptions.DefaultCredentialsError here must
    # be caught and turned into a clean ValueError, not left to traceback
    # uncaught all the way to the CLI's top level.
    fake_module = types.ModuleType("google.cloud.translate")

    class _FailingClient:
        def __init__(self):
            raise RuntimeError("Your default credentials were not found.")

    fake_module.TranslationServiceClient = _FailingClient
    monkeypatch.setitem(sys.modules, "google.cloud.translate", fake_module)
    monkeypatch.setitem(sys.modules, "google.cloud", sys.modules.get("google.cloud", types.ModuleType("google.cloud")))
    monkeypatch.setitem(sys.modules, "google", sys.modules.get("google", types.ModuleType("google")))

    with pytest.raises(ValueError, match="authenticate"):
        GoogleTranslateEngine(project="my-project")


def test_get_engine_uses_registry():
    client = _FakeV3Client(response_text="Hola")
    engine = get_engine("google-translate", project="my-project", client=client)
    assert engine.translate("Hello", "en", "es") == "Hola"


def test_does_not_support_generation():
    assert GoogleTranslateEngine.SUPPORTS_GENERATION is False
