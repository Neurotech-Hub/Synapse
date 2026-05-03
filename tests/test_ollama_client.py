"""Unit tests for ollama_client parsing (no running daemon)."""


def test_run_identity_llm_uses_json_format_by_default(monkeypatch) -> None:
    from app.ingest import ollama_client

    calls: list[tuple[bool, dict | None]] = []

    def capture(_prompt: str, *, model=None, json_format: bool = False, options=None):
        calls.append((json_format, options))
        return (
            '{"research_focus":[],"methods":[],"keywords":[],"current_projects":[],'
            '"funding_signals":[],"collab_openness_score":0.5,"notes":"n"}'
        )

    monkeypatch.setattr(ollama_client, "generate_non_stream", capture)
    monkeypatch.delenv("SYNAPSE_OLLAMA_IDENTITY_JSON_FORMAT", raising=False)
    monkeypatch.delenv("SYNAPSE_OLLAMA_IDENTITY_OPTIONS", raising=False)
    monkeypatch.delenv("SYNAPSE_OLLAMA_IDENTITY_NUM_CTX", raising=False)
    parsed, raw = ollama_client.run_identity_llm("x")
    assert calls[0][0] is True
    assert isinstance(calls[0][1], dict) and calls[0][1].get("num_ctx") == 32768
    assert parsed is not None and parsed.get("notes") == "n"
    assert '{"research_focus"' in raw


def test_run_identity_llm_skips_num_ctx_when_disabled(monkeypatch) -> None:
    from app.ingest import ollama_client

    got: dict | None | str = "unset"

    def capture(_prompt: str, *, model=None, json_format: bool = False, options=None):
        nonlocal got
        got = options
        return "{}"

    monkeypatch.setattr(ollama_client, "generate_non_stream", capture)
    monkeypatch.setenv("SYNAPSE_OLLAMA_IDENTITY_NUM_CTX", "0")
    monkeypatch.delenv("SYNAPSE_OLLAMA_IDENTITY_OPTIONS", raising=False)
    ollama_client.run_identity_llm("z")
    assert got is None


def test_try_enrich_lead_parses_json_in_markdown_fence(monkeypatch) -> None:
    from app.ingest import ollama_client

    raw = '''```json
{"headline": "h", "angle": "a", "outreach_snippet": "o", "hub_tags": "x,y"}
```
'''
    monkeypatch.setattr(ollama_client, "generate_non_stream", lambda _prompt: raw)
    got = ollama_client.try_enrich_lead("t", "u", "s")
    assert got == {
        "headline": "h",
        "angle": "a",
        "outreach_snippet": "o",
        "hub_tags": "x,y",
    }
