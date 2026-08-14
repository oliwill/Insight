"""LLM 增强客户端测试 —— web/llm_client"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config
from web import llm_client


def test_disabled_when_no_api_key(monkeypatch):
    monkeypatch.setattr(Config, "LLM_API_KEY", None)
    assert llm_client.llm_available() is False
    assert llm_client.enhance_summary("TEST.US", "Test", {}, 70.0, "Wait") is None


def test_success_returns_content(monkeypatch):
    monkeypatch.setattr(Config, "LLM_API_KEY", "sk-test")
    monkeypatch.setattr(Config, "LLM_BASE_URL", "https://api.deepseek.com")

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "### 核心观点\n测试观点"}}]}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(llm_client.requests, "post", fake_post)
    result = llm_client.enhance_summary(
        "TEST.US", "Test Co", {"stock_info": {"price": 10}}, 70.0, "Wait"
    )
    assert result == "### 核心观点\n测试观点"
    assert captured["url"].endswith("/chat/completions")
    assert captured["timeout"] == 60


def test_http_error_returns_none(monkeypatch):
    monkeypatch.setattr(Config, "LLM_API_KEY", "sk-test")

    def fail_post(url, headers, json, timeout):
        import requests

        raise requests.RequestException("boom")

    monkeypatch.setattr(llm_client.requests, "post", fail_post)
    assert llm_client.enhance_summary("TEST.US", "Test Co", {}, 70.0, "Wait") is None


def test_malformed_response_returns_none(monkeypatch):
    monkeypatch.setattr(Config, "LLM_API_KEY", "sk-test")

    class BadResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"unexpected": "shape"}

    monkeypatch.setattr(llm_client.requests, "post", lambda *a, **k: BadResponse())
    assert llm_client.enhance_summary("TEST.US", "Test Co", {}, 70.0, "Wait") is None
