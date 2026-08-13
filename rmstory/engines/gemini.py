"""
Gemini-backed TranslationEngine, via Google's `google-genai` SDK. Not a
hard dependency of rmstory -- install with `pip install "rmstory[gemini]"`.

Supports both ways of calling Gemini, auto-selected the same way the SDK
itself does:

    - The free option: the Gemini Developer API, authenticated with an API
      key from Google AI Studio (`api_key=` or the `GEMINI_API_KEY` /
      `GOOGLE_API_KEY` environment variable).
    - The account-based option: Vertex AI, authenticated against a Google
      Cloud project via Application Default Credentials (`project=` /
      `GOOGLE_CLOUD_PROJECT`, plus `GOOGLE_GENAI_USE_VERTEXAI=true` or an
      explicit `vertexai=True`).

Both modes share the same `generate_content` call once the client is
built, so `translate()` itself doesn't need to know which one is active.
"""

import os

from ..exceptions import TranslationError
from .base import TranslationEngine

DEFAULT_MODEL = "gemini-2.0-flash"

_PROMPT = (
    "Translate the following text from {from_lang} to {to_lang}. "
    "Output only the translated text -- no explanation, preamble, or "
    "surrounding quotation marks.\n\n{text}"
)


def _env_flag(name):
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


class GeminiEngine(TranslationEngine):
    def __init__(
        self,
        api_key=None,
        project=None,
        location=None,
        vertexai=None,
        model=None,
        client=None,
    ):
        """
        Args:
            api_key: Gemini Developer API key (free tier). Falls back to
                GEMINI_API_KEY, then GOOGLE_API_KEY.
            project: GCP project id, for the account-based Vertex AI path.
                Falls back to GOOGLE_CLOUD_PROJECT.
            location: Vertex AI region. Falls back to GOOGLE_CLOUD_LOCATION,
                then "us-central1".
            vertexai: Force Vertex AI mode on/off. Falls back to the
                GOOGLE_GENAI_USE_VERTEXAI environment variable; if that's
                also unset, Vertex mode is used whenever a project is
                available, otherwise the API-key mode is used.
            model: Gemini model name. Falls back to RMSTORY_GEMINI_MODEL,
                then DEFAULT_MODEL.
            client: A pre-built google.genai.Client, for tests or callers
                that already manage their own client. When given, all
                other credential arguments are ignored.

        Raises:
            ImportError: If the `google-genai` package isn't installed and
                `client` wasn't given.
            ValueError: If neither an API key nor a project is available.
        """
        self.model = model or os.environ.get("RMSTORY_GEMINI_MODEL", DEFAULT_MODEL)

        if client is not None:
            self._client = client
            return

        client_kwargs = self._resolve_client_kwargs(api_key, project, location, vertexai)

        try:
            from google import genai
        except ImportError as exc:
            raise ImportError(
                "the gemini engine requires the google-genai package: "
                "pip install \"rmstory[gemini]\""
            ) from exc

        self._client = genai.Client(**client_kwargs)

    @staticmethod
    def _resolve_client_kwargs(api_key, project, location, vertexai):
        """
        Work out which of the two ways to authenticate with Gemini to use,
        and the google.genai.Client kwargs for it. Split out from __init__
        so this selection logic is testable without needing the real SDK
        installed or mocking Python's import machinery.

        Raises:
            ValueError: If neither credential path is available.
        """
        project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        use_vertex = vertexai
        if use_vertex is None:
            use_vertex = _env_flag("GOOGLE_GENAI_USE_VERTEXAI") or bool(project)

        if use_vertex:
            if not project:
                raise ValueError(
                    "gemini engine in Vertex AI mode needs a GCP project: "
                    "pass project= or set GOOGLE_CLOUD_PROJECT"
                )
            location = location or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            return {"vertexai": True, "project": project, "location": location}

        api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "gemini engine needs credentials: either an API key "
                "(api_key=, GEMINI_API_KEY, or GOOGLE_API_KEY -- the free "
                "Gemini Developer API) or a GCP project (project= or "
                "GOOGLE_CLOUD_PROJECT -- Vertex AI via your Google Cloud account)"
            )
        return {"api_key": api_key}

    def translate(self, text, from_lang, to_lang):
        prompt = _PROMPT.format(from_lang=from_lang, to_lang=to_lang, text=text)
        try:
            response = self._client.models.generate_content(model=self.model, contents=prompt)
        except Exception as exc:
            raise TranslationError("gemini request failed: {}".format(exc)) from exc

        translated = (getattr(response, "text", None) or "").strip()
        if not translated:
            raise TranslationError("gemini returned an empty translation")
        return translated
