"""
Verify Ollama is installed and usable for Synapse (HTTP API).

These tests skip when the daemon is down or models are not pulled.
Uses stdlib only (no requests dependency).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

import pytest

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")

TAGS_TIMEOUT_SEC = 5
GENERATE_TIMEOUT_SEC = 120
EMBEDDINGS_TIMEOUT_SEC = 60


def _model_base_name(ollama_name: str) -> str:
    """e.g. llama3.2:latest -> llama3.2"""
    return ollama_name.split(":", 1)[0].strip()


def _get_json(url: str, *, timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode()
    return json.loads(body)


def _post_json(url: str, payload: dict[str, Any], *, timeout: float) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = resp.status
        body = resp.read().decode()
    return status, json.loads(body)


def _tags_or_skip() -> dict[str, Any]:
    try:
        return _get_json(f"{OLLAMA_HOST}/api/tags", timeout=TAGS_TIMEOUT_SEC)
    except urllib.error.URLError as e:
        pytest.skip(f"Ollama not reachable at {OLLAMA_HOST}/api/tags: {e}")
    except TimeoutError:
        pytest.skip(f"Ollama tags request timed out at {OLLAMA_HOST}")


def _tags_contain_model(tags: dict[str, Any], want: str) -> bool:
    want_base = _model_base_name(want)
    for m in tags.get("models") or []:
        name = m.get("name") or ""
        if _model_base_name(name) == want_base:
            return True
    return False


@pytest.fixture(scope="module")
def ollama_tags() -> dict[str, Any]:
    """Tags JSON from Ollama; skips entire module if daemon is down."""
    return _tags_or_skip()


@pytest.mark.ollama
def test_ollama_lists_models(ollama_tags: dict[str, Any]) -> None:
    assert "models" in ollama_tags
    assert isinstance(ollama_tags["models"], list)


@pytest.mark.ollama
def test_ollama_instruct_model_pulled(ollama_tags: dict[str, Any]) -> None:
    if not _tags_contain_model(ollama_tags, OLLAMA_MODEL):
        pytest.skip(
            f"Model '{OLLAMA_MODEL}' not in ollama tags; run: ollama pull {OLLAMA_MODEL}"
        )


@pytest.mark.ollama
@pytest.mark.slow
def test_ollama_try_enrich_lead_simulated_rss_item(ollama_tags: dict[str, Any]) -> None:
    """End-to-end check: Synapse lead prompt → Ollama → JSON parseable like ingest pipeline."""
    if not _tags_contain_model(ollama_tags, OLLAMA_MODEL):
        pytest.skip(
            f"Model '{OLLAMA_MODEL}' not in ollama tags; run: ollama pull {OLLAMA_MODEL}"
        )
    from app.ingest.ollama_client import try_enrich_lead

    result = try_enrich_lead(
        title="Acme Labs ships open-source widget for edge AI",
        link="https://example.com/blog/acme-widget-announcement",
        snippet="The 1.0 release targets researchers; benchmarks show 2x throughput on M-series Macs.",
    )
    assert result is not None, (
        "Lead enrichment returned None (unparseable JSON or network error). "
        "Ensure the model follows the JSON-only prompt; see app/ingest/ollama_client.py."
    )
    assert isinstance(result, dict)
    # Pipeline uses .get() per field; model should still populate the contract keys.
    expected_keys = frozenset({"headline", "angle", "outreach_snippet", "hub_tags"})
    assert expected_keys <= result.keys(), (
        f"Expected keys {expected_keys}, got {frozenset(result.keys())}"
    )


@pytest.mark.ollama
@pytest.mark.slow
def test_ollama_generate_non_stream(ollama_tags: dict[str, Any]) -> None:
    if not _tags_contain_model(ollama_tags, OLLAMA_MODEL):
        pytest.skip(
            f"Model '{OLLAMA_MODEL}' not in ollama tags; run: ollama pull {OLLAMA_MODEL}"
        )
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": "Reply with exactly: OK",
        "stream": False,
    }
    status, body = _post_json(
        f"{OLLAMA_HOST}/api/generate",
        payload,
        timeout=GENERATE_TIMEOUT_SEC,
    )
    assert status == 200
    assert "response" in body
    assert isinstance(body["response"], str)
    assert len(body["response"].strip()) > 0


@pytest.mark.ollama
def test_ollama_embeddings_optional(ollama_tags: dict[str, Any]) -> None:
    if not _tags_contain_model(ollama_tags, OLLAMA_EMBED_MODEL):
        pytest.skip(
            f"Embed model '{OLLAMA_EMBED_MODEL}' not pulled; optional: "
            f"ollama pull {OLLAMA_EMBED_MODEL}"
        )
    payload = {"model": OLLAMA_EMBED_MODEL, "prompt": "test"}
    status, body = _post_json(
        f"{OLLAMA_HOST}/api/embeddings",
        payload,
        timeout=EMBEDDINGS_TIMEOUT_SEC,
    )
    assert status == 200
    assert "embedding" in body
    assert isinstance(body["embedding"], list)
    assert len(body["embedding"]) > 0
