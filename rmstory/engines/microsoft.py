"""
Microsoft Translator (Azure AI Translator)-backed TranslationEngine, via
its plain REST API -- no SDK/extra dependency needed.

Free (F0) and paid (S1+) tiers use the same credential shape: a
subscription key, optionally paired with the resource's region (required
for regional resources; a "Global" resource doesn't need one). There's no
separate account-based mode modeled here -- Azure AD/managed-identity auth
exists but pulls in a materially bigger dependency (azure-identity) for a
niche case; a subscription key covers the common path for both tiers, the
same way the deepl engine's single auth_key does.
"""

import json
import os
import urllib.request
import uuid

from ..exceptions import TranslationError
from .base import TranslationEngine, call_with_retry

_DEFAULT_ENDPOINT = "https://api.cognitive.microsofttranslator.com"


def _default_http_post(url, headers, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


class MicrosoftTranslatorEngine(TranslationEngine):
    def __init__(self, api_key=None, region=None, endpoint=None, http_post=None):
        """
        Args:
            api_key: An Azure AI Translator subscription key. Falls back
                to AZURE_TRANSLATOR_KEY.
            region: The resource's region, required for regional resources
                (not for a "Global" resource). Falls back to
                AZURE_TRANSLATOR_REGION.
            endpoint: API base URL, for sovereign clouds or testing. Falls
                back to AZURE_TRANSLATOR_ENDPOINT, then the public global
                endpoint.
            http_post: A `(url, headers, payload) -> response_list`
                callable used instead of the real HTTP call -- for tests.

        Raises:
            ValueError: If no subscription key is available.
        """
        api_key = api_key or os.environ.get("AZURE_TRANSLATOR_KEY")
        if not api_key:
            raise ValueError(
                "microsoft-translator engine needs credentials: pass "
                "api_key= or set AZURE_TRANSLATOR_KEY (an Azure AI "
                "Translator subscription key -- the same parameter for "
                "both the free F0 and paid tiers)"
            )
        self._api_key = api_key
        self._region = region or os.environ.get("AZURE_TRANSLATOR_REGION")
        self._endpoint = endpoint or os.environ.get("AZURE_TRANSLATOR_ENDPOINT", _DEFAULT_ENDPOINT)
        self._http_post = http_post or _default_http_post

    def translate(self, text, from_lang, to_lang):
        url = "{}/translate?api-version=3.0&from={}&to={}".format(
            self._endpoint, from_lang, to_lang
        )
        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
            "Content-Type": "application/json",
            "X-ClientTraceId": str(uuid.uuid4()),
        }
        if self._region:
            headers["Ocp-Apim-Subscription-Region"] = self._region

        try:
            body = call_with_retry(lambda: self._http_post(url, headers, [{"Text": text}]))
        except Exception as exc:
            raise TranslationError("microsoft-translator request failed: {}".format(exc)) from exc

        try:
            translated = body[0]["translations"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslationError(
                "microsoft-translator returned an unexpected response: {}".format(body)
            ) from exc

        translated = translated.strip()
        if not translated:
            raise TranslationError("microsoft-translator returned an empty translation")
        return translated
