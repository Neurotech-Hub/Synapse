"""Unit tests for ollama_client parsing (no running daemon)."""


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
