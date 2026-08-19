"""
DeepSeek-backed TranslationEngine, via its official OpenAI-compatible REST
API -- no SDK, just a plain HTTP call (see _openai_chat.py for the shared
request/response shape). DeepSeek's models (V3, R1) are open-weight;
api.deepseek.com is DeepSeek's own hosted, official, pay-as-you-go
endpoint for them -- not a scrape of any consumer chat UI.

Also implements `generate(prompt)` (SUPPORTS_GENERATION = True) for
free-form text -- see rmstory.generation.
"""

import os

from ..exceptions import TranslationError
from . import _openai_chat
from .base import TranslationEngine, call_with_retry

_DEFAULT_URL = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-chat"  # DeepSeek-V3

_TRANSLATE_PROMPT = (
    "Translate the following text from {from_lang} to {to_lang}. "
    "Output only the translated text -- no explanation, preamble, or "
    "surrounding quotation marks.\n\n{text}"
)


class DeepSeekEngine(TranslationEngine):
    SUPPORTS_GENERATION = True

    def __init__(self, api_key=None, base_url=None, model=None, http_post=None):
        """
        Args:
            api_key: A DeepSeek API key. Falls back to DEEPSEEK_API_KEY.
            base_url: API base URL. Falls back to RMSTORY_DEEPSEEK_URL,
                then DeepSeek's own official endpoint.
            model: Model name. Falls back to RMSTORY_DEEPSEEK_MODEL, then
                "deepseek-chat" (DeepSeek-V3; use "deepseek-reasoner" for R1).
            http_post: A `(url, payload_dict) -> response_dict` callable
                used instead of the real HTTP call -- for tests. When
                given, `api_key` isn't required.

        Raises:
            ValueError: If no API key is available and `http_post` wasn't
                given.
        """
        self._base_url = (base_url or os.environ.get("RMSTORY_DEEPSEEK_URL", _DEFAULT_URL)).rstrip("/")
        self._model = model or os.environ.get("RMSTORY_DEEPSEEK_MODEL", _DEFAULT_MODEL)

        if http_post is not None:
            self._http_post = http_post
            return

        api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError(
                "deepseek engine needs credentials: pass api_key= or set "
                "DEEPSEEK_API_KEY (from https://platform.deepseek.com)"
            )
        self._http_post = lambda url, payload: _openai_chat.default_http_post(url, payload, api_key)

    def translate(self, text, from_lang, to_lang):
        prompt = _TRANSLATE_PROMPT.format(from_lang=from_lang, to_lang=to_lang, text=text)
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
            raise TranslationError("deepseek request failed: {}".format(exc)) from exc

        text = _openai_chat.extract_message(body)
        if text is None:
            raise TranslationError("deepseek returned an unexpected response: {}".format(body))

        text = text.strip()
        if not text:
            raise TranslationError("deepseek returned an empty response")
        return text
