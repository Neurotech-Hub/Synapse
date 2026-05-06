"""Unit tests for LLM provider env routing (no network)."""

from __future__ import annotations


def test_identity_defaults_to_openai_when_key_set(monkeypatch) -> None:
    from app.ingest import llm_client

    monkeypatch.delenv("SYNAPSE_LLM_IDENTITY_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert llm_client.identity_provider() == "openai"


def test_identity_respects_explicit_ollama(monkeypatch) -> None:
    from app.ingest import llm_client

    monkeypatch.setenv("SYNAPSE_LLM_IDENTITY_PROVIDER", "ollama")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert llm_client.identity_provider() == "ollama"


def test_run_identity_ollama_path(monkeypatch) -> None:
    from app.ingest import llm_client, ollama_client

    monkeypatch.setenv("SYNAPSE_LLM_IDENTITY_PROVIDER", "ollama")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    calls: list[bool] = []

    def fake_gen(prompt: str, *, json_format: bool = False, options=None):
        calls.append(json_format)
        return '{"notes":"ok"}'

    monkeypatch.setattr(ollama_client, "generate_non_stream", fake_gen)
    parsed, raw = llm_client.run_identity_llm("x")
    assert parsed is not None and parsed.get("notes") == "ok"
    assert calls == [True]


def test_public_feed_curate_label_follows_provider(monkeypatch) -> None:
    from app.ingest import llm_client

    monkeypatch.setenv("SYNAPSE_LLM_PUBLIC_FEED_PROVIDER", "openai")
    monkeypatch.setenv("SYNAPSE_OPENAI_PUBLIC_FEED_MODEL", "gpt-4o-mini")
    assert "gpt" in llm_client.public_feed_curate_model_label().lower()
