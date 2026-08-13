"""
Baidu Translate (通用翻译API)-backed TranslationEngine, via its plain REST
API -- no SDK/extra dependency needed, just stdlib hashlib for the
required request signature.

Baidu's auth is a different shape from every other engine here: an APPID
+ secret key pair, with each request signed as
md5(appid + query + salt + secret_key) rather than a bearer token or API
key header -- that's the integration cost flagged when this engine was
proposed. Both the free ("Personal", a modest daily character quota) and
paid tiers use this same APPID/secret pair, so there's no separate
account-based mode to model.
"""

import hashlib
import json
import os
import random
import urllib.parse
import urllib.request

from ..exceptions import TranslationError
from .base import TranslationEngine

_ENDPOINT = "https://fanyi-api.baidu.com/api/trans/vip/translate"

# Baidu's language codes mostly aren't bare ISO 639-1 -- a handful of
# common ones deviate (Japanese, Korean, French, ...). Best-effort map for
# the common cases, not exhaustive; anything not listed falls through as
# the bare (region-stripped) lowercase tag, which is correct for most of
# the rest (en, es, de, ru, ...).
_LANG_MAP = {
    "ja": "jp",
    "ko": "kor",
    "fr": "fra",
    "es": "spa",
    "ar": "ara",
    "vi": "vie",
}


def _to_baidu_lang(tag):
    primary = tag.split("-")[0].lower()
    return _LANG_MAP.get(primary, primary)


def _default_http_get(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


class BaiduEngine(TranslationEngine):
    def __init__(self, appid=None, secret_key=None, http_get=None):
        """
        Args:
            appid: Baidu Translate APPID. Falls back to
                BAIDU_TRANSLATE_APPID.
            secret_key: Baidu Translate secret key. Falls back to
                BAIDU_TRANSLATE_SECRET_KEY.
            http_get: A `(url) -> response_dict` callable used instead of
                the real HTTP call -- for tests.

        Raises:
            ValueError: If either credential is missing.
        """
        appid = appid or os.environ.get("BAIDU_TRANSLATE_APPID")
        secret_key = secret_key or os.environ.get("BAIDU_TRANSLATE_SECRET_KEY")
        if not appid or not secret_key:
            raise ValueError(
                "baidu engine needs credentials: appid=/BAIDU_TRANSLATE_APPID "
                "and secret_key=/BAIDU_TRANSLATE_SECRET_KEY (both the free "
                "Personal tier and paid Baidu Translate accounts use this "
                "same pair)"
            )
        self._appid = appid
        self._secret_key = secret_key
        self._http_get = http_get or _default_http_get

    def translate(self, text, from_lang, to_lang):
        salt = str(random.randint(32768, 65536))
        sign_raw = "{}{}{}{}".format(self._appid, text, salt, self._secret_key)
        sign = hashlib.md5(sign_raw.encode("utf-8")).hexdigest()

        params = {
            "q": text,
            "from": _to_baidu_lang(from_lang),
            "to": _to_baidu_lang(to_lang),
            "appid": self._appid,
            "salt": salt,
            "sign": sign,
        }
        url = "{}?{}".format(_ENDPOINT, urllib.parse.urlencode(params))

        try:
            body = self._http_get(url)
        except Exception as exc:
            raise TranslationError("baidu request failed: {}".format(exc)) from exc

        if "error_code" in body:
            raise TranslationError(
                "baidu returned an error ({}): {}".format(
                    body.get("error_code"), body.get("error_msg")
                )
            )

        try:
            translated = body["trans_result"][0]["dst"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslationError(
                "baidu returned an unexpected response: {}".format(body)
            ) from exc

        translated = translated.strip()
        if not translated:
            raise TranslationError("baidu returned an empty translation")
        return translated
