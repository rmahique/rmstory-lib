"""
DeepL-backed TranslationEngine, via the official `deepl` SDK. Not a hard
dependency of rmstory -- install with `pip install "rmstory[deepl]"`.

DeepL's free and paid (Pro) tiers use the same kind of credential -- an
auth key -- and differ only in the key's suffix (":fx" on free-tier keys)
and API host, both of which the `deepl` SDK detects and routes
automatically. There's no separate "account-based" mode to model here,
unlike Gemini/Google Translate.
"""

import os

from ..exceptions import TranslationError
from .base import TranslationEngine, call_with_retry


def _to_deepl_lang(tag):
    """
    DeepL's language codes are mostly uppercase BCP-47-ish tags (EN, ES,
    DE, PT-BR, ...); a plain uppercase of our lowercase BCP 47 tag covers
    the common cases. DeepL rejects a region-qualified *source* language
    (e.g. "EN-US" is a valid target but not a valid source) -- translating
    from a region-qualified tag needs the bare language passed instead,
    which this helper doesn't second-guess.
    """
    return tag.upper()


class DeepLEngine(TranslationEngine):
    def __init__(self, auth_key=None, client=None):
        """
        Args:
            auth_key: A DeepL API auth key (free or Pro -- same parameter
                either way). Falls back to the DEEPL_AUTH_KEY environment
                variable.
            client: A pre-built deepl.Translator, for tests or callers
                that already manage their own client. When given,
                `auth_key` is ignored.

        Raises:
            ImportError: If the `deepl` package isn't installed and
                `client` wasn't given.
            ValueError: If no auth key is available.
        """
        if client is not None:
            self._client = client
            return

        auth_key = auth_key or os.environ.get("DEEPL_AUTH_KEY")
        if not auth_key:
            raise ValueError(
                "deepl engine needs credentials: pass auth_key= or set "
                "DEEPL_AUTH_KEY (from your DeepL account -- the same "
                "parameter for both the free and Pro tiers)"
            )

        try:
            import deepl
        except ImportError as exc:
            raise ImportError(
                "the deepl engine requires the deepl package, which isn't available "
                "as a system package on any distro (it's DeepL's own PyPI-only SDK) "
                "-- install it once with: pip install \"rmstory[deepl]\""
            ) from exc

        self._client = deepl.Translator(auth_key)

    def translate(self, text, from_lang, to_lang):
        try:
            result = call_with_retry(
                lambda: self._client.translate_text(
                    text,
                    source_lang=_to_deepl_lang(from_lang),
                    target_lang=_to_deepl_lang(to_lang),
                )
            )
        except Exception as exc:
            raise TranslationError("deepl request failed: {}".format(exc)) from exc

        translated = (getattr(result, "text", None) or "").strip()
        if not translated:
            raise TranslationError("deepl returned an empty translation")
        return translated
