"""Thin Ollama HTTP client (stdlib). Failures propagate to callers for graceful fallback."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
GENERATE_TIMEOUT = 120.0


def ollama_available() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3):
            pass
        return True
    except (urllib.error.URLError, TimeoutError):
        return False


def generate_non_stream(prompt: str, *, model: str | None = None) -> str:
    m = model or OLLAMA_MODEL
    payload = {"model": m, "prompt": prompt, "stream": False}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=GENERATE_TIMEOUT) as resp:
        body = json.loads(resp.read().decode())
    return (body.get("response") or "").strip()


def try_enrich_lead(title: str, link: str, snippet: str) -> dict[str, Any] | None:
    prompt = (
        "Return ONLY compact JSON without markdown fences. Keys exactly: "
        'headline, angle, outreach_snippet, hub_tags (comma-separated string).\n'
        f"Title: {title}\nURL: {link}\nSnippet: {snippet}"
    )
    try:
        text = generate_non_stream(prompt)
        return json.loads(text)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, TypeError):
        return None
