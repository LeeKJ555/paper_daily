from __future__ import annotations

import pytest

from paper_daily.models import Paper
from paper_daily.summarizer import summarize_paper


def test_missing_deepseek_key_mentions_configured_env(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    config = {
        "run": {"require_openai_key": True},
        "summary": {
            "provider": "openai-compatible",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com",
        },
    }
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        summarize_paper(Paper(paper_id="p", title="Kernel"), config)


def test_openai_compatible_provider_uses_chat_completions(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    class Message:
        content = "summary"

    class Choice:
        message = Message()

    class Completions:
        def create(self, **kwargs):
            assert kwargs["model"] == "deepseek-chat"
            assert kwargs["messages"][0]["role"] == "system"
            return type("Response", (), {"choices": [Choice()]})()

    class Chat:
        completions = Completions()

    class FakeOpenAI:
        def __init__(self, api_key, base_url=None):
            assert api_key == "test-key"
            assert base_url == "https://api.deepseek.com"
            self.chat = Chat()

    monkeypatch.setattr("paper_daily.summarizer.OpenAI", FakeOpenAI)
    config = {
        "run": {"require_openai_key": True},
        "summary": {
            "provider": "openai-compatible",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com",
        },
    }
    assert summarize_paper(Paper(paper_id="p", title="Kernel"), config) == "summary"
