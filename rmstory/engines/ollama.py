"""
Ollama-backed TranslationEngine, via its local REST API -- no SDK, no API
key, no external account. Ollama runs open-weight models (Llama, Mistral,
Qwen, DeepSeek-R1, ...) entirely on this machine; this engine only talks
to the already-running `ollama serve` daemon, the same way libretranslate.py
talks to a self-hosted LibreTranslate instance.

Unlike every other engine here, there is no meaningful default model --
which model is usable depends entirely on what's been `ollama pull`ed on
this machine, so a model must be given explicitly (model= or
RMSTORY_OLLAMA_MODEL) rather than falling back to a name that would just
fail the same way, later, at request time instead of at construction.

Also implements `generate(prompt)` (SUPPORTS_GENERATION = True) for
free-form text -- see rmstory.generation.
"""

import json
import os
import urllib.request

from ..exceptions import TranslationError
from .base import TranslationEngine, call_with_retry

_DEFAULT_URL = "http://localhost:11434"

_TRANSLATE_PROMPT = (
    "Translate the following text from {from_lang} to {to_lang}. "
    "Output only the translated text -- no explanation, preamble, or "
    "surrounding quotation marks.\n\n{text}"
)


def _default_http_post(url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


class OllamaEngine(TranslationEngine):
    SUPPORTS_GENERATION = True

    def __init__(self, base_url=None, model=None, http_post=None):
        """
        Args:
            base_url: The Ollama server's base URL. Falls back to
                RMSTORY_OLLAMA_URL, then the standard local default
                "http://localhost:11434" (`ollama serve`'s own default).
            model: Name of a model already pulled on this Ollama instance
                (e.g. "llama3.1", "qwen2.5", "deepseek-r1"). Falls back to
                RMSTORY_OLLAMA_MODEL.
            http_post: A `(url, payload_dict) -> response_dict` callable
                used instead of the real HTTP call -- for tests.

        Raises:
            ValueError: If no model is given -- there's no safe default to
                fall back to (it depends entirely on what's been pulled).
        """
        self._base_url = (base_url or os.environ.get("RMSTORY_OLLAMA_URL", _DEFAULT_URL)).rstrip("/")
        self._model = model or os.environ.get("RMSTORY_OLLAMA_MODEL")
        self._http_post = http_post or _default_http_post

        if not self._model:
            raise ValueError(
                "ollama engine needs a model: pass model= or set "
                "RMSTORY_OLLAMA_MODEL, to a model already pulled on this "
                "Ollama instance (e.g. `ollama pull llama3.1`)"
            )

    def translate(self, text, from_lang, to_lang):
        prompt = _TRANSLATE_PROMPT.format(from_lang=from_lang, to_lang=to_lang, text=text)
        return self._complete(prompt)

    def generate(self, prompt):
        return self._complete(prompt)

    def _complete(self, prompt):
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }

        try:
            body = call_with_retry(lambda: self._http_post("{}/api/chat".format(self._base_url), payload))
        except Exception as exc:
            raise TranslationError("ollama request failed: {}".format(exc)) from exc

        try:
            text = body["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise TranslationError("ollama returned an unexpected response: {}".format(body)) from exc

        text = text.strip()
        if not text:
            raise TranslationError("ollama returned an empty response")
        return text
