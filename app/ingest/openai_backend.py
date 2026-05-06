"""OpenAI Chat Completions backend for JSON-oriented LLM tasks."""

from __future__ import annotations

import importlib.util
import os
import sys
from typing import Any

from app.ingest.llm_common import parse_model_json_object

# Default models (override via env)
DEFAULT_IDENTITY_MODEL = "gpt-4o-mini"
DEFAULT_LEAD_MODEL = "gpt-4o-mini"
DEFAULT_PUBLIC_FEED_MODEL = "gpt-4o-mini"


def _client():
    exe = sys.executable or "python3"
    if importlib.util.find_spec("openai") is None:
        raise RuntimeError(
            "The `openai` PyPI package is not installed for the Python interpreter running "
            f"Synapse ({exe}). Install it in that same environment, e.g. "
            f"{exe} -m pip install openai"
        )
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError(
            f"Could not import OpenAI from the `openai` package (interpreter: {exe}). "
            f"Try: {exe} -m pip install --upgrade openai"
        ) from e
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=key)


def openai_identity_timeout() -> float:
    raw = (os.environ.get("SYNAPSE_OPENAI_IDENTITY_TIMEOUT_SEC") or "600").strip()
    try:
        t = float(raw)
    except ValueError:
        t = 600.0
    return max(30.0, min(t, 3600.0))


def openai_chat_json(
    user_prompt: str,
    *,
    model: str | None = None,
    system_prompt: str | None = None,
    timeout: float | None = None,
    max_completion_tokens: int | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """Returns (assistant_content_or_None, telemetry).

    Telemetry keys: model, prompt_tokens, completion_tokens, total_tokens, error (optional).
    """

    m = (model or DEFAULT_IDENTITY_MODEL).strip() or DEFAULT_IDENTITY_MODEL
    tmo = openai_identity_timeout() if timeout is None else float(timeout)
    client = _client()
    messages: list[dict[str, str]] = []
    if system_prompt and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": user_prompt})

    kwargs: dict[str, Any] = {
        "model": m,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "timeout": tmo,
    }
    if max_completion_tokens is not None and max_completion_tokens > 0:
        kwargs["max_completion_tokens"] = int(max_completion_tokens)

    telem: dict[str, Any] = {"model": m}
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as exc:
        telem["error"] = str(exc)
        return None, telem

    choice = resp.choices[0].message if resp.choices else None
    content = (choice.content or "").strip() if choice else ""
    u = getattr(resp, "usage", None)
    if u is not None:
        telem["prompt_tokens"] = getattr(u, "prompt_tokens", None)
        telem["completion_tokens"] = getattr(u, "completion_tokens", None)
        telem["total_tokens"] = getattr(u, "total_tokens", None)
    return content, telem


def run_openai_identity_llm(prompt: str) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    """Identity JSON prompt -> (dict|None, raw_text, telemetry)."""

    model = (os.environ.get("SYNAPSE_OPENAI_IDENTITY_MODEL") or DEFAULT_IDENTITY_MODEL).strip() or DEFAULT_IDENTITY_MODEL
    max_tok_raw = (os.environ.get("SYNAPSE_OPENAI_IDENTITY_MAX_COMPLETION_TOKENS") or "8192").strip()
    try:
        max_ct = int(max_tok_raw)
    except ValueError:
        max_ct = 8192
    max_ct = max(256, min(max_ct, 128_000))

    content, telem = openai_chat_json(
        prompt,
        model=model,
        system_prompt=os.environ.get("SYNAPSE_OPENAI_IDENTITY_SYSTEM") or None,
        max_completion_tokens=max_ct,
        timeout=openai_identity_timeout(),
    )
    if content is None:
        return None, "", telem
    parsed = parse_model_json_object(content)
    return parsed, content, telem


def run_openai_lead_report_llm(prompt: str, *, json_format: bool = True) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    model = (os.environ.get("SYNAPSE_OPENAI_LEAD_MODEL") or DEFAULT_LEAD_MODEL).strip() or DEFAULT_LEAD_MODEL
    tmo = float(os.environ.get("SYNAPSE_OPENAI_LEAD_TIMEOUT_SEC") or "900")
    tmo = max(60.0, min(tmo, 7200.0))
    if not json_format:
        # Rare path: plain text
        client = _client()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            timeout=tmo,
        )
        text = (resp.choices[0].message.content or "").strip()
        return parse_model_json_object(text), {"model": model}
    content, telem = openai_chat_json(prompt, model=model, timeout=tmo, max_completion_tokens=16_384)
    if not content:
        return None, telem
    return parse_model_json_object(content), telem


def run_openai_public_feed_curate_llm(prompt: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    model = (os.environ.get("SYNAPSE_OPENAI_PUBLIC_FEED_MODEL") or DEFAULT_PUBLIC_FEED_MODEL).strip() or DEFAULT_PUBLIC_FEED_MODEL
    tmo = float(os.environ.get("SYNAPSE_OPENAI_PUBLIC_FEED_TIMEOUT_SEC") or "180")
    tmo = max(30.0, min(tmo, 1200.0))
    content, telem = openai_chat_json(prompt, model=model, timeout=tmo, max_completion_tokens=8192)
    if not content:
        return None, telem
    return parse_model_json_object(content), telem
