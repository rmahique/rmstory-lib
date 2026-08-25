"""
deep-translator-backed TranslationEngine. Wraps the `deep-translator`
package, which itself fronts several free/keyed translation services --
Google's keyless web endpoint (the default), DeepL, MyMemory, and
LibreTranslate. Not a hard dependency of rmstory -- install with
`pip install "rmstory[deep-translator]"`.

Unlike the `google-translate` and `deepl` engines, which call each
vendor's own API with that vendor's credentials, the default `google`
provider here needs no key at all -- it uses the same free endpoint a
browser does. That makes it the walk-up-and-use option when no account
is available, at the cost of the endpoint's own rate limits and its
occasional passthrough: for a language pair it can't handle it may echo
the source text back rather than raising, so a caller that must trust the
result should verify the output isn't just the input.
"""

import os

from ..exceptions import TranslationError
from .base import TranslationEngine, call_with_retry

# Providers this engine exposes, mapped to the class to import from
# deep-translator. "google" and "mymemory" are keyless; "deepl" requires
# an api_key; "libre" takes one only if the target instance enforces keys.
_PROVIDERS = {
    "google": "GoogleTranslator",
    "deepl": "DeepL",
    "mymemory": "MyMemoryTranslator",
    "libre": "LibreTranslator",
}

# deep-translator mostly wants ISO 639-1 codes; a few of our lowercase
# BCP 47 tags need a specific regional or legacy form.
_LANG_ALIASES = {
    "zh": "zh-CN",
    "zh-hans": "zh-CN",
    "zh-hant": "zh-TW",
    "he": "iw",
    "jv": "jw",
}


def _to_provider_lang(tag):
    """Map a BCP 47 tag to the code deep-translator expects (best-effort)."""
    if not tag or tag.lower() in ("auto", "und"):
        return "auto"
    tag = tag.lower()
    return _LANG_ALIASES.get(tag, tag)


def _mark_if_transient(exc):
    """
    deep-translator raises its own exception types for rate-limiting and
    server-side failures (TooManyRequests, ServerException, RequestError)
    that carry no HTTP status attribute, so base.call_with_retry can't see
    them as retryable on its own. Tag those with a status_code it does
    recognise (503) so a momentary rate-limit is retried rather than
    aborting the run; everything else (a bad language pair, malformed
    input) is left untouched and surfaces immediately.
    """
    if type(exc).__name__ in ("TooManyRequests", "ServerException", "RequestError"):
        exc.status_code = 503


class DeepTranslatorEngine(TranslationEngine):
    def __init__(self, provider="google", api_key=None, translator_factory=None):
        """
        Args:
            provider: Which deep-translator backend to use -- "google"
                (default, keyless), "deepl", "mymemory", or "libre".
            api_key: Credential for the providers that need one. "deepl"
                requires it (falls back to DEEPL_AUTH_KEY); "libre" takes
                it only if the target instance enforces keys; "google" and
                "mymemory" ignore it.
            translator_factory: A `(provider, source, target, api_key) ->
                object with .translate(text)` callable used instead of the
                real deep-translator classes -- for tests, or callers that
                want to supply their own backend. Defaults to building the
                real backend.

        Raises:
            ImportError: If deep-translator isn't installed and no
                translator_factory was given.
            ValueError: If `provider` is unknown, or "deepl" is chosen
                without an api_key.
        """
        provider = (provider or "google").lower()
        if provider not in _PROVIDERS:
            raise ValueError(
                "unknown deep-translator provider {!r} -- available: {}".format(
                    provider, ", ".join(sorted(_PROVIDERS))
                )
            )
        self.provider = provider

        if provider == "deepl":
            api_key = api_key or os.environ.get("DEEPL_AUTH_KEY")
            if not api_key:
                raise ValueError(
                    "deep-translator's deepl provider needs credentials: pass "
                    "api_key= or set DEEPL_AUTH_KEY"
                )
        self._api_key = api_key

        if translator_factory is not None:
            self._factory = translator_factory
        else:
            self._factory = _default_translator_factory
            # Fail fast with a helpful message if the package is missing,
            # rather than only at the first translate() call.
            try:
                import deep_translator  # noqa: F401
            except ImportError as exc:
                raise ImportError(
                    "the deep-translator engine requires the deep-translator "
                    "package -- install it with: "
                    "pip install \"rmstory[deep-translator]\""
                ) from exc

    def translate(self, text, from_lang, to_lang):
        source = _to_provider_lang(from_lang)
        target = _to_provider_lang(to_lang)
        try:
            translator = self._factory(self.provider, source, target, self._api_key)
        except ImportError:
            raise
        except Exception as exc:
            raise TranslationError(
                "deep-translator ({}) could not be built: {}".format(self.provider, exc)
            ) from exc

        def _call():
            try:
                return translator.translate(text)
            except Exception as exc:
                _mark_if_transient(exc)
                raise

        try:
            result = call_with_retry(_call)
        except Exception as exc:
            raise TranslationError(
                "deep-translator ({}) request failed: {}".format(self.provider, exc)
            ) from exc

        translated = (result or "").strip()
        if not translated:
            raise TranslationError(
                "deep-translator ({}) returned an empty translation".format(self.provider)
            )
        return translated


def _default_translator_factory(provider, source, target, api_key):
    """Build a real deep-translator backend for `provider`."""
    import deep_translator

    cls = getattr(deep_translator, _PROVIDERS[provider])
    if provider == "deepl":
        return cls(api_key=api_key, source=source, target=target, use_free_api=True)
    if provider == "libre" and api_key:
        return cls(source=source, target=target, api_key=api_key)
    # google, mymemory, and keyless libre.
    return cls(source=source, target=target)
