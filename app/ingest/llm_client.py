"""Route high-level LLM tasks to OpenAI or Ollama based on environment."""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from typing import Any

from app.ingest import ollama_client as oc
from app.ingest.llm_common import parse_model_json_object

logger = logging.getLogger(__name__)


def _truthy(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


def identity_provider() -> str:
    explicit = (os.environ.get("SYNAPSE_LLM_IDENTITY_PROVIDER") or "").strip().lower()
    if explicit in ("openai", "ollama"):
        return explicit
    return "openai" if (os.environ.get("OPENAI_API_KEY") or "").strip() else "ollama"


def lead_report_provider() -> str:
    e = (os.environ.get("SYNAPSE_LLM_LEAD_PROVIDER") or "").strip().lower()
    if e in ("openai", "ollama"):
        return e
    return "ollama"


def public_feed_curate_provider() -> str:
    e = (os.environ.get("SYNAPSE_LLM_PUBLIC_FEED_PROVIDER") or "").strip().lower()
    if e in ("openai", "ollama"):
        return e
    return "ollama"


def identity_llm_model_label() -> str:
    if identity_provider() == "openai":
        m = (os.environ.get("SYNAPSE_OPENAI_IDENTITY_MODEL") or "gpt-4o-mini").strip()
        return m or "gpt-4o-mini"
    return oc.OLLAMA_MODEL


def lead_report_model_label() -> str:
    if lead_report_provider() == "openai":
        m = (os.environ.get("SYNAPSE_OPENAI_LEAD_MODEL") or "gpt-4o-mini").strip()
        return m or "gpt-4o-mini"
    return oc.OLLAMA_MODEL


def public_feed_curate_model_label() -> str:
    if public_feed_curate_provider() == "openai":
        m = (os.environ.get("SYNAPSE_OPENAI_PUBLIC_FEED_MODEL") or "gpt-4o-mini").strip()
        return m or "gpt-4o-mini"
    return oc.OLLAMA_MODEL


def _identity_fallback_ollama_enabled() -> bool:
    return _truthy(os.environ.get("SYNAPSE_LLM_IDENTITY_FALLBACK_OLLAMA", "1"))


def _run_identity_ollama(prompt: str) -> tuple[dict[str, Any] | None, str]:
    text, ok = oc._generate_prompt_text(
        prompt,
        json_format=oc._identity_uses_ollama_json_format(),
        options=oc._identity_ollama_options(),
    )
    if not ok:
        return None, ""
    parsed = parse_model_json_object(text)
    return parsed, text


def run_identity_llm(prompt: str) -> tuple[dict[str, Any] | None, str]:
    """Person / org / building persona JSON prompt → ``(dict|None, raw_model_text_if_any)``."""

    prov = identity_provider()
    if prov == "openai":
        try:
            from app.ingest.openai_backend import run_openai_identity_llm

            parsed, raw, telem = run_openai_identity_llm(prompt)
            if any(
                k in telem for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            ):
                logger.info("openai identity telemetry: %s", telem)
            return parsed, raw
        except Exception as exc:
            logger.warning("OpenAI identity failed: %s", exc)
            if _identity_fallback_ollama_enabled():
                return _run_identity_ollama(prompt)
            return None, ""
    return _run_identity_ollama(prompt)


def run_lead_report_llm(prompt: str, *, json_format: bool = True) -> dict[str, Any] | None:
    prov = lead_report_provider()
    if prov == "openai":
        try:
            from app.ingest.openai_backend import run_openai_lead_report_llm

            parsed, _telem = run_openai_lead_report_llm(prompt, json_format=json_format)
            return parsed
        except Exception as exc:
            logger.warning("OpenAI lead report failed: %s", exc)
            if _truthy(os.environ.get("SYNAPSE_LLM_LEAD_FALLBACK_OLLAMA", "1")):
                return oc.ollama_run_lead_report_llm(prompt, json_format=json_format)
            return None
    return oc.ollama_run_lead_report_llm(prompt, json_format=json_format)


def run_public_feed_curate_llm(prompt: str) -> dict[str, Any] | None:
    prov = public_feed_curate_provider()
    if prov == "openai":
        try:
            from app.ingest.openai_backend import run_openai_public_feed_curate_llm

            parsed, _telem = run_openai_public_feed_curate_llm(prompt)
            return parsed
        except Exception as exc:
            logger.warning("OpenAI public feed curation failed: %s", exc)
            if _truthy(os.environ.get("SYNAPSE_LLM_PUBLIC_FEED_FALLBACK_OLLAMA", "1")):
                return oc.ollama_run_public_feed_curate_llm(prompt)
            return None
    return oc.ollama_run_public_feed_curate_llm(prompt)


def openai_sdk_spec_available() -> bool:
    """True if the ``openai`` PyPI package is importable in this interpreter."""

    try:
        return importlib.util.find_spec("openai") is not None
    except (ValueError, ImportError):
        return False


def persona_rebuild_busy_footer_message() -> str:
    """One-line status while a persona POST is in flight (OpenAI vs Ollama)."""

    label = identity_llm_model_label()
    if identity_provider() == "openai":
        if not openai_sdk_spec_available():
            exe = sys.executable or "python3"
            return (
                f"OpenAI is selected but the `openai` package is not installed for this Python "
                f"({exe}). Install: {exe} -m pip install openai"
            )
        return f"Calling OpenAI ({label}) — leave this tab open."
    return f"Running Ollama ({label}) — leave this tab open."


def openai_identity_admin_status() -> dict[str, Any]:
    """Sidebar snapshot: OpenAI key presence and effective identity provider/model."""

    has_key = bool((os.environ.get("OPENAI_API_KEY") or "").strip())
    return {
        "configured": has_key,
        "identity_provider": identity_provider(),
        "identity_model": identity_llm_model_label(),
        "sdk_installed": openai_sdk_spec_available(),
    }
