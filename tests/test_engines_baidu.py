import hashlib
import urllib.parse

import pytest

from rmstory.engines import get_engine
from rmstory.engines.baidu import BaiduEngine, _to_baidu_lang
from rmstory.exceptions import TranslationError


def test_translate_with_injected_http_get_and_correct_signature():
    calls = []

    def fake_http_get(url):
        calls.append(url)
        return {"trans_result": [{"src": "Hello", "dst": "你好"}]}

    engine = BaiduEngine(appid="app123", secret_key="sekrit", http_get=fake_http_get)

    result = engine.translate("Hello", "en", "zh")

    assert result == "你好"
    url = calls[0]
    params = dict(urllib.parse.parse_qsl(url.split("?", 1)[1]))
    assert params["q"] == "Hello"
    assert params["from"] == "en"
    assert params["to"] == "zh"
    assert params["appid"] == "app123"
    expected_sign = hashlib.md5(
        "app123Hello{}sekrit".format(params["salt"]).encode("utf-8")
    ).hexdigest()
    assert params["sign"] == expected_sign


def test_language_code_mapping():
    assert _to_baidu_lang("ja") == "jp"
    assert _to_baidu_lang("ko") == "kor"
    assert _to_baidu_lang("fr") == "fra"
    assert _to_baidu_lang("en") == "en"
    assert _to_baidu_lang("de") == "de"
    assert _to_baidu_lang("pt-BR") == "pt"


def test_error_code_response_raises_translation_error():
    def fake_http_get(url):
        return {"error_code": "54001", "error_msg": "Invalid Sign"}

    engine = BaiduEngine(appid="app123", secret_key="sekrit", http_get=fake_http_get)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "zh")


def test_malformed_response_raises_translation_error():
    def fake_http_get(url):
        return {"unexpected": "shape"}

    engine = BaiduEngine(appid="app123", secret_key="sekrit", http_get=fake_http_get)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "zh")


def test_empty_response_raises_translation_error():
    def fake_http_get(url):
        return {"trans_result": [{"src": "Hello", "dst": ""}]}

    engine = BaiduEngine(appid="app123", secret_key="sekrit", http_get=fake_http_get)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "zh")


def test_underlying_error_wrapped():
    def fake_http_get(url):
        raise OSError("network down")

    engine = BaiduEngine(appid="app123", secret_key="sekrit", http_get=fake_http_get)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "zh")


def test_missing_credentials_raises_value_error(monkeypatch):
    monkeypatch.delenv("BAIDU_TRANSLATE_APPID", raising=False)
    monkeypatch.delenv("BAIDU_TRANSLATE_SECRET_KEY", raising=False)
    with pytest.raises(ValueError):
        BaiduEngine()


def test_partial_credentials_raises_value_error(monkeypatch):
    monkeypatch.delenv("BAIDU_TRANSLATE_SECRET_KEY", raising=False)
    with pytest.raises(ValueError):
        BaiduEngine(appid="app123")


def test_credentials_from_env(monkeypatch):
    monkeypatch.setenv("BAIDU_TRANSLATE_APPID", "env-app")
    monkeypatch.setenv("BAIDU_TRANSLATE_SECRET_KEY", "env-secret")

    def fake_http_get(url):
        assert "appid=env-app" in url
        return {"trans_result": [{"dst": "你好"}]}

    engine = BaiduEngine(http_get=fake_http_get)
    assert engine.translate("Hello", "en", "zh") == "你好"


def test_get_engine_uses_registry():
    engine = get_engine(
        "baidu",
        appid="app123",
        secret_key="sekrit",
        http_get=lambda url: {"trans_result": [{"dst": "你好"}]},
    )
    assert engine.translate("Hello", "en", "zh") == "你好"
