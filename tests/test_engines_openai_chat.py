import json

from rmstory.engines import _openai_chat


class _FakeResponse:
    def __init__(self, body):
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return self._body


def test_default_http_post_sends_bearer_auth_and_json_body(monkeypatch):
    captured = {}

    def fake_urlopen(request):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["content_type"] = request.get_header("Content-type")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse({"choices": [{"message": {"content": "Hola"}}]})

    monkeypatch.setattr(_openai_chat.urllib.request, "urlopen", fake_urlopen)

    result = _openai_chat.default_http_post(
        "http://example.test/chat/completions", {"model": "m", "messages": []}, "secret-key"
    )

    assert result == {"choices": [{"message": {"content": "Hola"}}]}
    assert captured["url"] == "http://example.test/chat/completions"
    assert captured["auth"] == "Bearer secret-key"
    assert captured["content_type"] == "application/json"
    assert captured["body"] == {"model": "m", "messages": []}


def test_extract_message_returns_text():
    body = {"choices": [{"message": {"role": "assistant", "content": "Hola"}}]}
    assert _openai_chat.extract_message(body) == "Hola"


def test_extract_message_returns_none_on_unexpected_shape():
    assert _openai_chat.extract_message({"error": "bad request"}) is None
    assert _openai_chat.extract_message({"choices": []}) is None
    assert _openai_chat.extract_message("not even a dict") is None
