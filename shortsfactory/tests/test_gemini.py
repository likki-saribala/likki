import json

import httpx
import pytest

from shortsfactory.script import GeminiScriptWriter, _gemini_schema

GOOD = {"title": "T", "scenes": [{"text": "Short line.", "query": "sea", "claim": "c"}] * 4, "hashtags": ["a"]}


def _client(*texts):
    seen = []
    queue = list(texts)

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        assert req.headers["x-goog-api-key"] == "k"
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": queue.pop(0)}]}}]})

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def test_schema_uppercased():
    s = _gemini_schema({"type": "object", "properties": {"a": {"type": "array", "items": {"type": "string"}}}})
    assert s["type"] == "OBJECT" and s["properties"]["a"]["items"]["type"] == "STRING"


def test_valid_script_parsed():
    c, seen = _client(json.dumps(GOOD))
    assert GeminiScriptWriter("k", "m", c).write("x").title == "T"
    assert "models/m:generateContent" in str(seen[0].url)


def test_timeout_retries_once_then_fails_loudly():
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ReadTimeout("slow", request=req)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(GOOD)}]}}]})

    c = httpx.Client(transport=httpx.MockTransport(handler))
    assert GeminiScriptWriter("k", "m", c).write("x").title == "T" and len(calls) == 2

    def always(req):
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(RuntimeError, match="timed out twice"):
        GeminiScriptWriter("k", "m", httpx.Client(transport=httpx.MockTransport(always))).write("x")


def test_http_error_includes_google_message():
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404, text='{"error":{"message":"model gone"}}')))
    with pytest.raises(RuntimeError, match="404.*'m'.*model gone"):
        GeminiScriptWriter("k", "m", c).write("x")


def test_retries_once_then_succeeds_and_then_fails_loudly():
    c, seen = _client("not json", json.dumps(GOOD))
    assert GeminiScriptWriter("k", "m", c).write("x").title == "T"
    assert "rejected" in json.loads(seen[1].content)["contents"][0]["parts"][0]["text"]
    c, _ = _client("nope", "still nope")
    with pytest.raises(RuntimeError, match="invalid twice"):
        GeminiScriptWriter("k", "m", c).write("x")
