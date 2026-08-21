"""
Kimi-backed TranslationEngine, via Moonshot AI's official OpenAI-compatible
REST API -- no SDK, just a plain HTTP call (see _openai_chat.py for the
shared request/response shape). Kimi K2 is open-weight; Moonshot's own
API is the hosted, official endpoint for it -- not a scrape of any
consumer chat UI (kimi.com).

Moonshot has two regional endpoints with separate accounts/keys --
mainland China and international -- so RMSTORY_KIMI_URL is the one
credential-adjacent setting worth overriding explicitly rather than
guessing from locale. Defaults to the international endpoint.

Also implements `generate(prompt)` (SUPPORTS_GENERATION = True) for
free-form text -- see rmstory.generation.
"""

import os

from ..exceptions import TranslationError
from . import _openai_chat
from .base import TranslationEngine, build_translate_prompt, call_with_retry

_DEFAULT_URL = "https://api.moonshot.ai/v1"
# "kimi-latest" is Moonshot's own perpetually-repointed alias for its
# current recommended model -- not a rmstory-picked version, same
# reasoning as gemini.py's DEFAULT_MODEL. Pin an exact version instead
# via model= or RMSTORY_KIMI_MODEL for reproducible output across a
# model rollover.
_DEFAULT_MODEL = "kimi-latest"


class KimiEngine(TranslationEngine):
    SUPPORTS_GENERATION = True

    def __init__(self, api_key=None, base_url=None, model=None, http_post=None):
        """
        Args:
            api_key: A Moonshot AI API key. Falls back to MOONSHOT_API_KEY.
            base_url: API base URL. Falls back to RMSTORY_KIMI_URL, then
                Moonshot's international endpoint -- set RMSTORY_KIMI_URL
                to "https://api.moonshot.cn/v1" for a mainland China
                account/key instead.
            model: Model name. Falls back to RMSTORY_KIMI_MODEL, then
                "kimi-latest".
            http_post: A `(url, payload_dict) -> response_dict` callable
                used instead of the real HTTP call -- for tests. When
                given, `api_key` isn't required.

        Raises:
            ValueError: If no API key is available and `http_post` wasn't
                given.
        """
        self._base_url = (base_url or os.environ.get("RMSTORY_KIMI_URL", _DEFAULT_URL)).rstrip("/")
        self._model = model or os.environ.get("RMSTORY_KIMI_MODEL", _DEFAULT_MODEL)

        if http_post is not None:
            self._http_post = http_post
            return

        api_key = api_key or os.environ.get("MOONSHOT_API_KEY")
        if not api_key:
            raise ValueError(
                "kimi engine needs credentials: pass api_key= or set "
                "MOONSHOT_API_KEY (from https://platform.moonshot.ai)"
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
            raise TranslationError("kimi request failed: {}".format(exc)) from exc

        text = _openai_chat.extract_message(body)
        if text is None:
            raise TranslationError("kimi returned an unexpected response: {}".format(body))

        text = text.strip()
        if not text:
            raise TranslationError("kimi returned an empty response")
        return text
