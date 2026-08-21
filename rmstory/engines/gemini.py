"""
Gemini-backed TranslationEngine, via Google's `google-genai` SDK. Not a
hard dependency of rmstory -- install with `pip install "rmstory[gemini]"`.

Supports both ways of calling Gemini:

    - The free option: the Gemini Developer API, authenticated with an API
      key from Google AI Studio (`api_key=` or the `GEMINI_API_KEY` /
      `GOOGLE_API_KEY` environment variable).
    - The account-based option: Vertex AI, authenticated against a Google
      Cloud project via Application Default Credentials (`project=` /
      `GOOGLE_CLOUD_PROJECT`, plus `GOOGLE_GENAI_USE_VERTEXAI=true` or an
      explicit `vertexai=True`).

When neither mode is forced explicitly, an available API key wins -- a
bare `GOOGLE_CLOUD_PROJECT` alone (often already set for unrelated
reasons, e.g. `gcloud` config or the google-translate engine) doesn't
silently require full ADC/Vertex setup when a working API key is already
present. See `_resolve_client_kwargs` for the exact precedence.

Both modes share the same `generate_content` call once the client is
built, so `translate()` itself doesn't need to know which one is active.

Also implements `generate(prompt)` (SUPPORTS_GENERATION = True) for
free-form text -- see rmstory.generation -- since Gemini is a
general-purpose LLM, not just a translation API.
"""

import logging
import os

from ..exceptions import TranslationError
from .base import TranslationEngine, build_translate_prompt, call_with_retry

# google-genai logs a one-time WARNING-level notice on the first call
# recommending Chat.send_message over Models.generate_content for automatic
# function calling (AFC) -- irrelevant here, translate() never registers any
# tools/functions for the model to call, so there's nothing AFC-related for
# that advice to apply to. Python's logging has no handler configured by
# default, so this reaches stderr only via the "handler of last resort"
# (WARNING+ with no handler); raising this specific logger's level keeps
# genuine errors from the SDK visible while dropping this one benign notice.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

# "-latest" is Google's own perpetually-repointed alias for its current
# recommended Flash model -- not a rmstory-picked version. A pinned dated
# name (e.g. "gemini-2.0-flash") eventually gets retired server-side and
# starts hard-failing every call with a 404 telling you what to switch to;
# the alias avoids that maintenance burden by letting Google keep it
# current. Pin an exact version instead via model= or RMSTORY_GEMINI_MODEL
# if you need reproducible output across a model rollover.
DEFAULT_MODEL = "gemini-flash-latest"


def _env_flag(name):
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


class GeminiEngine(TranslationEngine):
    SUPPORTS_GENERATION = True

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
                also unset, an available API key is preferred (it's a
                deliberate, single-purpose signal), and Vertex mode is only
                auto-selected when a project is available and no API key is
                -- a bare GOOGLE_CLOUD_PROJECT (often already set for
                unrelated reasons) doesn't by itself require full ADC setup
                when a working API key is present.
            model: Gemini model name. Falls back to RMSTORY_GEMINI_MODEL,
                then DEFAULT_MODEL ("gemini-flash-latest", Google's own
                always-current alias -- see the module docstring).
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
                "the gemini engine requires the google-genai package, which isn't "
                "available as a system package on any distro (it's Google's own "
                "PyPI-only SDK) -- install it once with: "
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
        api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        use_vertex = vertexai
        if use_vertex is None:
            # An API key is a deliberate, single-purpose signal; GOOGLE_CLOUD_PROJECT
            # is commonly already set for unrelated reasons (gcloud config, the
            # google-translate engine's own Vertex mode) without the full ADC setup
            # Vertex AI needs, so a bare project alone shouldn't silently escalate
            # auth requirements when a working API key is already available. Force
            # Vertex explicitly via GOOGLE_GENAI_USE_VERTEXAI=true or vertexai=True.
            use_vertex = _env_flag("GOOGLE_GENAI_USE_VERTEXAI") or (bool(project) and not api_key)

        if use_vertex:
            if not project:
                raise ValueError(
                    "gemini engine in Vertex AI mode needs a GCP project: "
                    "pass project= or set GOOGLE_CLOUD_PROJECT"
                )
            location = location or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            return {"vertexai": True, "project": project, "location": location}

        if not api_key:
            raise ValueError(
                "gemini engine needs credentials: either an API key "
                "(api_key=, GEMINI_API_KEY, or GOOGLE_API_KEY -- the free "
                "Gemini Developer API) or a GCP project (project= or "
                "GOOGLE_CLOUD_PROJECT -- Vertex AI via your Google Cloud account)"
            )
        return {"api_key": api_key}

    def translate(self, text, from_lang, to_lang):
        prompt = build_translate_prompt(text, from_lang, to_lang)
        return self._complete(prompt)

    def generate(self, prompt):
        return self._complete(prompt)

    def _complete(self, prompt):
        try:
            response = call_with_retry(
                lambda: self._client.models.generate_content(model=self.model, contents=prompt)
            )
        except Exception as exc:
            raise TranslationError("gemini request failed: {}".format(exc)) from exc

        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise TranslationError("gemini returned an empty response")
        return text
