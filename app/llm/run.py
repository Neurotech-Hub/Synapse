from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.extensions import db
from app.llm.prompt_registry import (
    effective_prompt_provider,
    get_prompt_spec,
    prompt_input_fingerprint,
    render_prompt,
)
from app.models import LLMRun


def hash_text(text: str | None) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def estimate_tokens(text: str | None) -> int:
    # Lightweight estimate for logging/caps until provider telemetry is wired.
    return max(0, round(len(text or "") / 4))


def create_llm_run(
    prompt_name: str,
    variables: dict[str, Any],
    *,
    provider: str | None = None,
    model_name: str | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
    status: str = "queued",
    metadata: dict[str, Any] | None = None,
) -> tuple[LLMRun, str]:
    spec = get_prompt_spec(prompt_name)
    rendered = render_prompt(prompt_name, variables)
    run = LLMRun(
        prompt_name=spec.name,
        prompt_version=spec.version,
        provider=provider or effective_prompt_provider(prompt_name),
        model_name=model_name,
        input_fingerprint=prompt_input_fingerprint(prompt_name, variables),
        rendered_prompt_hash=hash_text(rendered),
        status=status,
        estimated_input_tokens=estimate_tokens(rendered),
        source_type=source_type,
        source_id=source_id,
        metadata_json=metadata or {},
    )
    db.session.add(run)
    db.session.flush()
    return run, rendered


def mark_llm_run_running(run: LLMRun) -> None:
    run.status = "running"


def complete_llm_run(
    run: LLMRun,
    output_text: str,
    *,
    validation_errors: list[str] | None = None,
    latency_ms: int | None = None,
    status: str | None = None,
) -> None:
    errors = validation_errors or []
    run.output_hash = hash_text(output_text)
    run.estimated_output_tokens = estimate_tokens(output_text)
    run.validation_errors_json = errors
    run.latency_ms = latency_ms
    run.status = status or ("validation_failed" if errors else "ok")
    run.completed_at = datetime.now(timezone.utc)


def fail_llm_run(run: LLMRun, error_message: str, *, latency_ms: int | None = None) -> None:
    run.status = "failed"
    run.error_message = error_message
    run.latency_ms = latency_ms
    run.completed_at = datetime.now(timezone.utc)
