"""
Mistral AI-backed TranslationEngine, via its official OpenAI-compatible
REST API -- no SDK, just a plain HTTP call (see _openai_chat.py for the
shared request/response shape). Mistral's flagship models are open-weight;
api.mistral.ai is Mistral's own hosted, official endpoint for them -- not
a scrape of any consumer chat UI.

Also implements `generate(prompt)` (SUPPORTS_GENERATION = True) for
free-form text -- see rmstory.generation.
"""

import os

from ..exceptions import TranslationError
from . import _openai_chat
from .base import TranslationEngine, build_translate_prompt, call_with_retry

_DEFAULT_URL = "https://api.mistral.ai/v1"
# "-latest" is Mistral's own perpetually-repointed alias for its current
# recommended flagship model -- not a rmstory-picked version, same
# reasoning as gemini.py's DEFAULT_MODEL. Pin an exact version instead via
# model= or RMSTORY_MISTRAL_MODEL for reproducible output across a
# model rollover.
_DEFAULT_MODEL = "mistral-large-latest"


class MistralEngine(TranslationEngine):
    SUPPORTS_GENERATION = True

    def __init__(self, api_key=None, base_url=None, model=None, http_post=None):
        """
        Args:
            api_key: A Mistral AI API key. Falls back to MISTRAL_API_KEY.
            base_url: API base URL. Falls back to RMSTORY_MISTRAL_URL,
                then Mistral's own official endpoint.
            model: Model name. Falls back to RMSTORY_MISTRAL_MODEL, then
                "mistral-large-latest" (see note above).
            http_post: A `(url, payload_dict) -> response_dict` callable
                used instead of the real HTTP call -- for tests. When
                given, `api_key` isn't required.

        Raises:
            ValueError: If no API key is available and `http_post` wasn't
                given.
        """
        self._base_url = (base_url or os.environ.get("RMSTORY_MISTRAL_URL", _DEFAULT_URL)).rstrip("/")
        self._model = model or os.environ.get("RMSTORY_MISTRAL_MODEL", _DEFAULT_MODEL)

        if http_post is not None:
            self._http_post = http_post
            return

        api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError(
                "mistral engine needs credentials: pass api_key= or set "
                "MISTRAL_API_KEY (from https://console.mistral.ai)"
            )
        self._http_post = lambda url, payload: _openai_chat.default_http_post(url, payload, api_key)

    def translate(self, text, from_lang, to_lang):
        prompt = build_translate_prompt(text, from_lang, to_lang)
        return self._complete(prompt)

    def generate(self, prompt):
        return self._complete(prompt)

    def _complete(self, prompt):
        payload = {"model": self._model, "messages": [{"role": "user", "content": prompt}]}

        try:
            body = call_with_retry(
                lambda: self._http_post("{}/chat/completions".format(self._base_url), payload)
            )
        except Exception as exc:
            raise TranslationError("mistral request failed: {}".format(exc)) from exc

        text = _openai_chat.extract_message(body)
        if text is None:
            raise TranslationError("mistral returned an unexpected response: {}".format(body))

        text = text.strip()
        if not text:
            raise TranslationError("mistral returned an empty response")
        return text
