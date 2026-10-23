"""Unit tests for src/agents/_llm_client.py -- entirely offline. Every test
mocks `requests.post` at the module level; none of these ever touches a
real network socket or a running Ollama server (that's tests/test_baseline_llm_smoke.py's job).
"""

from __future__ import annotations

import requests

from src.agents._llm_client import DEFAULT_BASE_URL, LLMClientError, OllamaLLMClient
import pytest


class _FakeResponse:
    def __init__(self, status_code=200, json_body=None, text="", json_error=False):
        self.status_code = status_code
        self._json_body = json_body
        self.text = text
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("not json")
        return self._json_body


def test_generate_returns_the_models_text_on_success(monkeypatch):
    def fake_post(url, json, timeout):
        assert url == f"{DEFAULT_BASE_URL}/api/generate"
        assert json["model"] == "qwen2.5:3b"
        assert json["stream"] is False
        return _FakeResponse(200, {"response": "hello", "model": "qwen2.5:3b", "done": True})

    monkeypatch.setattr("src.agents._llm_client.requests.post", fake_post)
    client = OllamaLLMClient(model="qwen2.5:3b")
    result = client.generate("a prompt")
    assert result.raw_text == "hello"
    assert result.model == "qwen2.5:3b"


def test_generate_raises_on_connection_error(monkeypatch):
    def fake_post(url, json, timeout):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr("src.agents._llm_client.requests.post", fake_post)
    client = OllamaLLMClient()
    with pytest.raises(LLMClientError, match="Could not reach Ollama"):
        client.generate("x")


def test_generate_raises_on_timeout(monkeypatch):
    def fake_post(url, json, timeout):
        raise requests.exceptions.Timeout("too slow")

    monkeypatch.setattr("src.agents._llm_client.requests.post", fake_post)
    client = OllamaLLMClient(timeout=5.0)
    with pytest.raises(LLMClientError, match="timed out"):
        client.generate("x")


def test_generate_raises_on_non_200_status(monkeypatch):
    def fake_post(url, json, timeout):
        return _FakeResponse(500, text="internal error")

    monkeypatch.setattr("src.agents._llm_client.requests.post", fake_post)
    client = OllamaLLMClient()
    with pytest.raises(LLMClientError, match="HTTP 500"):
        client.generate("x")


def test_generate_raises_on_invalid_json_body(monkeypatch):
    def fake_post(url, json, timeout):
        return _FakeResponse(200, json_error=True, text="not json at all")

    monkeypatch.setattr("src.agents._llm_client.requests.post", fake_post)
    client = OllamaLLMClient()
    with pytest.raises(LLMClientError, match="not valid JSON"):
        client.generate("x")


def test_generate_raises_on_empty_response_text(monkeypatch):
    def fake_post(url, json, timeout):
        return _FakeResponse(200, {"response": "   ", "model": "qwen2.5:3b"})

    monkeypatch.setattr("src.agents._llm_client.requests.post", fake_post)
    client = OllamaLLMClient()
    with pytest.raises(LLMClientError, match="empty response"):
        client.generate("x")
