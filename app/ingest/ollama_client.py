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
TAGS_TIMEOUT_SEC = 3.0


def fetch_ollama_tags(*, timeout: float | None = None) -> dict[str, Any] | None:
    """Parse JSON from GET /api/tags, or None if unreachable / invalid."""
    t = TAGS_TIMEOUT_SEC if timeout is None else timeout
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=t) as resp:
            body = resp.read().decode()
        data = json.loads(body)
        return data if isinstance(data, dict) else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, TypeError):
        return None


def _tag_base_name(ollama_name: str) -> str:
    return ollama_name.split(":", 1)[0].strip()


def _tags_include_model(tags: dict[str, Any], want: str) -> bool:
    want_base = _tag_base_name(want)
    for m in tags.get("models") or []:
        if not isinstance(m, dict):
            continue
        name = str(m.get("name") or "")
        if _tag_base_name(name) == want_base:
            return True
    return False


def ollama_available() -> bool:
    return fetch_ollama_tags() is not None


def ollama_admin_status() -> dict[str, Any]:
    """Snapshot for admin UI: API reachability and whether OLLAMA_MODEL is pulled."""
    tags = fetch_ollama_tags()
    if tags is None:
        return {
            "reachable": False,
            "model_ok": False,
            "host": OLLAMA_HOST,
            "model": OLLAMA_MODEL,
        }
    return {
        "reachable": True,
        "model_ok": _tags_include_model(tags, OLLAMA_MODEL),
        "host": OLLAMA_HOST,
        "model": OLLAMA_MODEL,
    }


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


def _parse_model_json_object(text: str) -> dict[str, Any] | None:
    """Parse a JSON object from model output; tolerate ``` fences and leading/trailing chatter."""
    t = (text or "").strip()
    if not t:
        return None
    if t.startswith("```"):
        rest = t[3:].lstrip()
        if rest.lower().startswith("json"):
            rest = rest[4:].lstrip("\n ")
        fence = rest.rfind("```")
        if fence != -1:
            rest = rest[:fence]
        t = rest.strip()
    try:
        data = json.loads(t)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(t[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return None


def try_summarize_html_page(
    *,
    url: str,
    page_title_guess: str | None,
    plaintext_excerpt: str,
    max_prompt_chars: int = 14000,
) -> dict[str, Any] | None:
    """LLM condensation for html_page ingestion. Expected keys: title, snippet (paragraphs OK)."""
    excerpt = (plaintext_excerpt or "")[:max_prompt_chars].strip()
    title_hint = (page_title_guess or "").strip()[:400]
    prompt = (
        "You distill public web pages for a research ingestion database. "
        "Return ONLY compact JSON without markdown fences. Keys exactly: "
        "title (short descriptive headline about this page/update), snippet (<= 4000 chars, "
        "main substance: what changed, key facts; no fluff, no preamble).\n"
        f"Page URL: {url}\nHTML title hint: {title_hint or '(none)'}\n"
        "Visible text excerpt (may be truncated):\n"
        f"{excerpt}"
    )
    try:
        text = generate_non_stream(prompt)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    return _parse_model_json_object(text)


def try_enrich_lead(title: str, link: str, snippet: str) -> dict[str, Any] | None:
    prompt = (
        "Return ONLY compact JSON without markdown fences. Keys exactly: "
        'headline, angle, outreach_snippet, hub_tags (comma-separated string).\n'
        f"Title: {title}\nURL: {link}\nSnippet: {snippet}"
    )
    try:
        text = generate_non_stream(prompt)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    return _parse_model_json_object(text)
