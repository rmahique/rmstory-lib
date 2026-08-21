"""The interface every translation engine backend implements."""

import random
import re
import subprocess
import time
import urllib.error

_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_BASE_DELAY = 1.0  # seconds
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Matches render.py's nested_placeholder() output (parser.py), e.g.
# `<span id="ch1.reveal.1"/>` -- a nested child's content is never inlined
# into its parent's stored translation, only this self-closing reference.
_NESTED_PLACEHOLDER_RE = re.compile(r'<span id="[^"]*"/>')

_PRESERVE_PLACEHOLDERS_NOTE = (
    " The text contains one or more placeholders of the exact form "
    '<span id="..."/> (self-closing, nothing between the tags) -- copy '
    "each one into your translation completely unchanged, in the same "
    "position relative to the surrounding words, without translating, "
    "removing, or altering the id inside it."
)


def build_translate_prompt(text, from_lang, to_lang):
    """
    The shared translate prompt every LLM-backed engine sends, appending
    `_PRESERVE_PLACEHOLDERS_NOTE` when `text` contains a nested span
    placeholder -- otherwise a model has no reason not to translate or
    merge it into the surrounding sentence like any other word, which
    render.py's rewrite_spans() then rejects (a stored translation must
    preserve a nested span's placeholder unchanged). Omitted when there's
    no placeholder so the common case (a leaf span, no nested children)
    keeps the plain, shorter prompt.
    """
    instruction = "Translate the following text from {} to {}.".format(from_lang, to_lang)
    if _NESTED_PLACEHOLDER_RE.search(text):
        instruction += _PRESERVE_PLACEHOLDERS_NOTE
    instruction += (
        " Output only the translated text -- no explanation, preamble, "
        "or surrounding quotation marks.\n\n{}".format(text)
    )
    return instruction


def _is_transient(exc):
    """
    True for a failure worth retrying: rate-limiting or server-side overload
    (429/5xx, or an SDK exception that says so directly, e.g. DeepL's own
    `should_retry`), or a connection-level/timeout failure (network
    timeout, refused, reset, or a subprocess.TimeoutExpired from the
    claude-code engine's CLI call) rather than a real, permanent rejection
    (bad credentials, malformed request, empty/unexpected response). Every
    engine's SDK or urllib.error.HTTPError exposes the status under one of
    `code`, `status_code`, or `http_status_code` -- checking all three
    covers google-genai's APIError, google-api-core's GoogleAPICallError,
    and urllib.error.HTTPError uniformly without importing any of them here.
    """
    if getattr(exc, "should_retry", False):
        return True
    for attr in ("code", "status_code", "http_status_code"):
        status = getattr(exc, attr, None)
        if isinstance(status, int) and status in _RETRYABLE_STATUS_CODES:
            return True
    if isinstance(exc, (TimeoutError, ConnectionError, subprocess.TimeoutExpired)):
        return True
    # A connection-level urllib failure (DNS, refused, reset) has no HTTP
    # status at all -- URLError covers this, but HTTPError (a URLError
    # subclass with a real status code) was already handled above via `code`.
    return isinstance(exc, urllib.error.URLError) and not isinstance(exc, urllib.error.HTTPError)


def call_with_retry(fn, max_attempts=_DEFAULT_MAX_ATTEMPTS, base_delay=_DEFAULT_BASE_DELAY, sleep=None):
    """
    Call `fn()` and return its result, retrying with exponential backoff +
    jitter when the failure looks transient (see `_is_transient`) -- so a
    momentary rate-limit or server overload doesn't abort an entire
    extract/translate run over one span. A non-transient failure (bad
    credentials, malformed request, ...) is raised immediately, on the
    first attempt, since retrying it would just fail the same way.

    The final exception (transient or not) is re-raised as-is once attempts
    are exhausted, so callers wrap it into TranslationError exactly as they
    would without retrying at all.

    `sleep` defaults to `time.sleep`, looked up at call time rather than
    bound as a default argument, so tests can patch `base.time.sleep`
    directly (including through a real engine's `translate()`, which never
    passes `sleep=` itself) instead of needing every call site to thread a
    test double through.
    """
    sleep = sleep or time.sleep
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except Exception as exc:
            if attempt >= max_attempts or not _is_transient(exc):
                raise
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, base_delay)
            sleep(delay)


class TranslationEngine:
    """
    A pluggable machine-translation backend.

    This is deliberately independent of the CLI and of translation storage
    -- it's a plain function-shaped interface other applications can call
    directly (`rmstory.engines.translate_text`), the same way multilang-lib
    keeps its own backend interface separate from `insert_data`/
    `retrieve_data`.
    """

    def translate(self, text, from_lang, to_lang):
        """
        Translate `text` from `from_lang` to `to_lang` (BCP 47 tags) and
        return the translated text.

        Raises:
            rmstory.exceptions.TranslationError: If the engine fails to
                produce a result.
        """
        raise NotImplementedError

    # Only engines backed by a general-purpose LLM can honor generate() --
    # a plain translate-this-string API (deepl, google-translate,
    # microsoft-translator, libretranslate, baidu) has nothing to call for
    # free-form text. False here is the correct default for all of those;
    # an LLM-backed engine (gemini, claude-code, ollama, deepseek, mistral,
    # qwen) overrides both this and generate() itself. Checked as a class
    # attribute (not requiring an instance) so callers -- e.g.
    # rmstory.generation -- can tell before spending credentials/a real
    # connection on building one.
    SUPPORTS_GENERATION = False

    def generate(self, prompt):
        """
        Generate free-form text from `prompt` -- no source text to
        transform, unlike translate(). Only implemented by engines with
        SUPPORTS_GENERATION True.

        Raises:
            NotImplementedError: If this engine doesn't support
                generation.
            rmstory.exceptions.TranslationError: If the engine fails to
                produce a result.
        """
        raise NotImplementedError(
            "{} does not support free-form text generation -- only "
            "LLM-backed engines do (SUPPORTS_GENERATION)".format(type(self).__name__)
        )
