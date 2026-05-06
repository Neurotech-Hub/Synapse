from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from flask import current_app, has_app_context

from app.extensions import db
from app.llm.providers import MockProvider, ProviderResult, default_model_for_provider, run_prompt_provider
from app.llm.run import complete_llm_run, create_llm_run, fail_llm_run, mark_llm_run_running
from app.llm.validation import StructuredOutputValidation, parse_and_validate_prompt_json
from app.models import LLMRun


@dataclass
class LLMExecutionResult:
    ok: bool
    run: LLMRun | None = None
    data: dict[str, Any] | None = None
    raw_text: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provider_result: ProviderResult | None = None


class LLMExecutionPolicyError(RuntimeError):
    pass


def execute_prompt(
    prompt_name: str,
    variables: dict[str, Any],
    *,
    provider: str | None = None,
    model_name: str | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
    allow_openai: bool = False,
    require_enabled: bool = True,
    mock_provider: MockProvider | None = None,
    auto_repair: bool = False,
) -> LLMExecutionResult:
    selected_provider = (provider or "").strip().lower() or None
    if selected_provider is None:
        from app.llm.prompt_registry import effective_prompt_provider

        selected_provider = effective_prompt_provider(prompt_name)
    if selected_provider == "auto":
        selected_provider = "ollama"

    try:
        _enforce_execution_policy(
            selected_provider,
            variables,
            require_enabled=require_enabled,
            allow_openai=allow_openai,
            mock_provider=mock_provider,
        )
        run, rendered = create_llm_run(
            prompt_name,
            variables,
            provider=selected_provider,
            model_name=model_name or default_model_for_provider(selected_provider),
            source_type=source_type,
            source_id=source_id,
            status="queued",
            metadata={"auto_repair": bool(auto_repair)},
        )
        mark_llm_run_running(run)
        db.session.flush()
    except Exception as exc:
        return LLMExecutionResult(ok=False, errors=[str(exc)])

    provider_result = run_prompt_provider(
        selected_provider,
        rendered,
        model_name=run.model_name,
        timeout_sec=_config_value("SYNAPSE_LLM_TIMEOUT_SEC", 90),
        json_format=True,
        mock_provider=mock_provider,
    )
    if not provider_result.ok:
        fail_llm_run(run, provider_result.error or "Provider returned no content.", latency_ms=provider_result.latency_ms)
        db.session.commit()
        return LLMExecutionResult(ok=False, run=run, errors=[run.error_message or "Provider failed."], provider_result=provider_result)

    validation = parse_and_validate_prompt_json(prompt_name, provider_result.raw_text)
    if not validation.ok and auto_repair:
        # Scaffold for a later sprint. Keep disabled by default and avoid hidden second model calls.
        validation.warnings.append("Automatic JSON repair is not enabled in this sprint.")
    complete_llm_run(
        run,
        provider_result.raw_text,
        validation_errors=validation.errors,
        latency_ms=provider_result.latency_ms,
    )
    if provider_result.telemetry:
        run.metadata_json = {**(run.metadata_json or {}), "provider_telemetry": provider_result.telemetry}
        if provider_result.telemetry.get("prompt_tokens") is not None:
            run.estimated_input_tokens = provider_result.telemetry.get("prompt_tokens")
        if provider_result.telemetry.get("completion_tokens") is not None:
            run.estimated_output_tokens = provider_result.telemetry.get("completion_tokens")
    db.session.commit()
    return LLMExecutionResult(
        ok=validation.ok,
        run=run,
        data=validation.data,
        raw_text=provider_result.raw_text,
        errors=validation.errors,
        warnings=validation.warnings,
        provider_result=provider_result,
    )


def _enforce_execution_policy(
    provider: str,
    variables: dict[str, Any],
    *,
    require_enabled: bool,
    allow_openai: bool,
    mock_provider: MockProvider | None,
) -> None:
    provider = (provider or "").strip().lower()
    if provider == "mock":
        if mock_provider is None:
            raise LLMExecutionPolicyError("Mock provider requires a mock_provider callable.")
        return
    if require_enabled and not bool(_config_value("SYNAPSE_LLM_SYNTHESIS_ENABLED", False)):
        raise LLMExecutionPolicyError("LLM synthesis is disabled by settings.")
    max_chars = int(_config_value("SYNAPSE_MAX_PROMPT_CHARS", 24_000))
    approx_chars = len(str(variables))
    if approx_chars > max_chars:
        raise LLMExecutionPolicyError(f"Prompt input exceeds SYNAPSE_MAX_PROMPT_CHARS ({max_chars}).")
    if provider == "openai":
        escalation_enabled = bool(_config_value("SYNAPSE_OPENAI_ESCALATION_ENABLED", False))
        if not allow_openai and not escalation_enabled:
            raise LLMExecutionPolicyError("OpenAI execution is disabled unless explicitly allowed.")
    if provider not in {"ollama", "openai"}:
        raise LLMExecutionPolicyError(f"Unsupported LLM provider: {provider}.")


def _config_value(name: str, default: Any) -> Any:
    if has_app_context():
        return current_app.config.get(name, default)
    return default
