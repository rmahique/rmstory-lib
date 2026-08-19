"""
Google Cloud Translation-backed TranslationEngine.

Two ways to call it, auto-selected the same way the Gemini engine picks
between its two modes:

    - The free-ish option: Basic Translation API (v2), authenticated with
      a plain API key (`api_key=` or GOOGLE_TRANSLATE_API_KEY). Calls the
      REST endpoint directly via the standard library -- no extra package
      needed for this mode.
    - The account-based option: Advanced Translation API (v3), against a
      Google Cloud project via Application Default Credentials (`project=`
      / GOOGLE_CLOUD_PROJECT -- the same env var the Gemini engine's
      Vertex AI mode uses, since it's the same kind of GCP credential).
      Needs the `google-cloud-translate` package: `pip install
      "rmstory[google-translate]"`.

Google Cloud Translation has no true walk-up-and-use free tier the way
Gemini's AI Studio does -- a v2 API key still comes from a GCP project
with the Translation API enabled and billing configured -- but the two
*credential shapes* (a bare API key vs. full ADC) mirror Gemini's free/
account split closely enough to model the same way, including the same
precedence: an available API key wins over a bare project, since
GOOGLE_CLOUD_PROJECT is often already set for unrelated reasons (gcloud
config, the gemini engine's own Vertex mode) without the ADC setup v3
needs. Pass `client=` directly to force v3 mode despite an API key
being set.
"""

import json
import os
import urllib.request

from ..exceptions import TranslationError
from .base import TranslationEngine, call_with_retry

_V2_ENDPOINT = "https://translation.googleapis.com/language/translate/v2"


def _default_http_post(url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


class GoogleTranslateEngine(TranslationEngine):
    def __init__(self, api_key=None, project=None, location=None, client=None, http_post=None):
        """
        Args:
            api_key: A Google Cloud API key with the Translation API
                enabled (Basic/v2). Falls back to GOOGLE_TRANSLATE_API_KEY.
                When available, this wins over `project`/GOOGLE_CLOUD_PROJECT
                -- a bare project is often already set for unrelated reasons
                (gcloud config, the gemini engine's own Vertex mode) without
                the ADC setup v3 needs, so it shouldn't by itself require
                that when a working API key is present (same reasoning as
                GeminiEngine's api-key-wins precedence).
            project: GCP project id (Advanced/v3, account-based). Falls
                back to GOOGLE_CLOUD_PROJECT. Only selects v3 mode when no
                API key is available; pass `client=` directly to force v3
                despite an API key being set.
            location: API region for v3. Falls back to
                GOOGLE_CLOUD_LOCATION, then "global".
            client: A pre-built google.cloud.translate.TranslationServiceClient
                for the v3 path -- for tests, or callers that already
                manage their own client. Forces v3 mode; pass `project`
                (or set GOOGLE_CLOUD_PROJECT) alongside it, since it's
                still needed to build the request path.
            http_post: A `(url, payload_dict) -> response_dict` callable
                used for the v2 path instead of the real REST call -- for
                tests. Defaults to an actual HTTP POST via urllib.

        Raises:
            ImportError: If v3 mode is selected and google-cloud-translate
                isn't installed.
            ValueError: If neither an API key nor a project is available,
                or v3 mode is selected but Application Default Credentials
                can't be resolved (TranslationServiceClient() validates ADC
                eagerly at construction time, unlike the gemini engine's
                lazy-auth SDK, so this is caught here rather than surfacing
                as an uncaught google.auth exception).
        """
        self.location = location or os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
        self._http_post = http_post or _default_http_post

        if client is not None:
            self._client = client
            self.project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
            self._mode = "v3"
            return

        api_key, project = self._resolve_credentials(api_key, project)
        if project and not api_key:
            self.project = project
            self._mode = "v3"
            try:
                from google.cloud import translate
            except ImportError as exc:
                raise ImportError(
                    "the google-translate engine's account-based mode requires the "
                    "google-cloud-translate package, which isn't available as a "
                    "system package on any distro (it's Google's own PyPI-only "
                    "SDK) -- install it once with: "
                    "pip install \"rmstory[google-translate]\""
                ) from exc
            try:
                self._client = translate.TranslationServiceClient()
            except Exception as exc:
                raise ValueError(
                    "google-translate engine's account-based mode failed to "
                    "authenticate: {} -- run `gcloud auth application-default "
                    "login` to set up Application Default Credentials, or use "
                    "the simpler api_key=/GOOGLE_TRANSLATE_API_KEY path "
                    "instead if you don't need the account-based (Vertex-style "
                    "GCP billing) mode".format(exc)
                ) from exc
        else:
            self._api_key = api_key
            self._mode = "v2"

    @staticmethod
    def _resolve_credentials(api_key, project):
        """
        Work out which of the two ways to authenticate to use. Split out
        from __init__ so this selection is testable without needing the
        real SDK installed -- same reasoning as GeminiEngine's
        _resolve_client_kwargs.
        """
        api_key = api_key or os.environ.get("GOOGLE_TRANSLATE_API_KEY")
        project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not api_key and not project:
            raise ValueError(
                "google-translate engine needs credentials: either an API "
                "key (api_key= or GOOGLE_TRANSLATE_API_KEY -- Basic/v2) or "
                "a GCP project (project= or GOOGLE_CLOUD_PROJECT -- "
                "Advanced/v3, account-based via Application Default Credentials)"
            )
        return api_key, project

    def translate(self, text, from_lang, to_lang):
        if self._mode == "v3":
            return self._translate_v3(text, from_lang, to_lang)
        return self._translate_v2(text, from_lang, to_lang)

    def _translate_v3(self, text, from_lang, to_lang):
        parent = "projects/{}/locations/{}".format(self.project, self.location)
        try:
            response = call_with_retry(
                lambda: self._client.translate_text(
                    request={
                        "parent": parent,
                        "contents": [text],
                        "mime_type": "text/plain",
                        "source_language_code": from_lang,
                        "target_language_code": to_lang,
                    }
                )
            )
        except Exception as exc:
            raise TranslationError("google-translate request failed: {}".format(exc)) from exc

        translations = getattr(response, "translations", None) or []
        if not translations:
            raise TranslationError("google-translate returned no translation")
        translated = (translations[0].translated_text or "").strip()
        if not translated:
            raise TranslationError("google-translate returned an empty translation")
        return translated

    def _translate_v2(self, text, from_lang, to_lang):
        url = "{}?key={}".format(_V2_ENDPOINT, self._api_key)
        payload = {"q": text, "source": from_lang, "target": to_lang, "format": "text"}
        try:
            body = call_with_retry(lambda: self._http_post(url, payload))
        except Exception as exc:
            raise TranslationError("google-translate request failed: {}".format(exc)) from exc

        try:
            translated = body["data"]["translations"][0]["translatedText"]
        except (KeyError, IndexError) as exc:
            raise TranslationError("google-translate returned an unexpected response") from exc

        translated = translated.strip()
        if not translated:
            raise TranslationError("google-translate returned an empty translation")
        return translated
