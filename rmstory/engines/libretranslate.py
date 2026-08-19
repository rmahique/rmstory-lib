"""
LibreTranslate-backed TranslationEngine, via its plain REST API -- no
SDK/extra dependency needed.

LibreTranslate is open-source and self-hostable; a self-hosted instance
with API_KEYS disabled needs no credential at all, which is the actually-
free, no-account option none of the other engines here offer. Public
hosted instances (libretranslate.com and various community mirrors)
typically do require an API key. There's no account-based mode to model
here -- everything is one base_url plus an optional key.
"""

import json
import os
import urllib.request

from ..exceptions import TranslationError
from .base import TranslationEngine, call_with_retry

_DEFAULT_URL = "http://localhost:5000"


def _default_http_post(url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


class LibreTranslateEngine(TranslationEngine):
    def __init__(self, base_url=None, api_key=None, http_post=None):
        """
        Args:
            base_url: The LibreTranslate instance's base URL (no trailing
                /translate). Falls back to LIBRETRANSLATE_URL, then the
                standard self-hosted default "http://localhost:5000" (e.g.
                `docker run -p 5000:5000 libretranslate/libretranslate`).
            api_key: Optional API key, only needed by instances that
                require one. Falls back to LIBRETRANSLATE_API_KEY.
            http_post: A `(url, payload_dict) -> response_dict` callable
                used instead of the real HTTP call -- for tests.
        """
        self._base_url = (base_url or os.environ.get("LIBRETRANSLATE_URL", _DEFAULT_URL)).rstrip("/")
        self._api_key = api_key or os.environ.get("LIBRETRANSLATE_API_KEY")
        self._http_post = http_post or _default_http_post

    def translate(self, text, from_lang, to_lang):
        payload = {"q": text, "source": from_lang, "target": to_lang, "format": "text"}
        if self._api_key:
            payload["api_key"] = self._api_key

        try:
            body = call_with_retry(lambda: self._http_post("{}/translate".format(self._base_url), payload))
        except Exception as exc:
            raise TranslationError("libretranslate request failed: {}".format(exc)) from exc

        try:
            translated = body["translatedText"]
        except (KeyError, TypeError) as exc:
            raise TranslationError(
                "libretranslate returned an unexpected response: {}".format(body)
            ) from exc

        translated = translated.strip()
        if not translated:
            raise TranslationError("libretranslate returned an empty translation")
        return translated
