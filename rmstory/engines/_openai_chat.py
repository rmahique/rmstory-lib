"""
Shared request/response shaping for the OpenAI-compatible chat completions
REST endpoint -- deepseek.py, mistral.py, and qwen.py all speak this exact
wire format (`POST {base_url}/chat/completions`, Bearer auth, response text
at `choices[0].message.content`), differing only in base URL, API key env
var, and default model. Not a TranslationEngine itself and not registered
in _ENGINES -- each of those three still subclasses TranslationEngine
directly and owns its own credentials/docstring/env vars, per
CONTRIBUTING.md; this only avoids three copies of identical request-
building and response-parsing code.
"""

import json
import urllib.request


def default_http_post(url, payload, api_key):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(api_key),
        },
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_message(body):
    """The assistant's reply text, or None if the response shape is unexpected."""
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
