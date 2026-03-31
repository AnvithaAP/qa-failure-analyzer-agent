import pytest

from src.llm import Analyzer


def test_analyzer_validates_provider_on_init(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    with pytest.raises(RuntimeError, match="Unsupported LLM_PROVIDER"):
        Analyzer()
