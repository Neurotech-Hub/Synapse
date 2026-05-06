from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Callable

from app.ingest import ollama_client
from app.ingest.openai_backend import openai_chat_json


@dataclass
class ProviderResult:
    raw_text: str
    provider: str
    model_name: str | None
    latency_ms: int | None = None
    error: str | None = None
    telemetry: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and bool((self.raw_text or "").strip())


MockProvider = Callable[[str, str | None], str]


def default_model_for_provider(provider: str) -> str | None:
    provider = (provider or "").strip().lower()
    if provider == "ollama":
        return os.environ.get("SYNAPSE_OLLAMA_GENERIC_MODEL") or ollama_client.OLLAMA_MODEL
    if provider == "openai":
        return os.environ.get("SYNAPSE_OPENAI_GENERIC_MODEL") or "gpt-4o-mini"
    if provider == "mock":
        return "mock"
    return None


def run_prompt_provider(
    provider: str,
    prompt: str,
    *,
    model_name: str | None = None,
    timeout_sec: int | float | None = None,
    json_format: bool = True,
    mock_provider: MockProvider | None = None,
) -> ProviderResult:
    provider = (provider or "").strip().lower()
    model = model_name or default_model_for_provider(provider)
    started = time.perf_counter()
    try:
        if provider == "mock":
            if mock_provider is None:
                raise RuntimeError("Mock provider requested but no mock_provider callable was supplied.")
            raw = mock_provider(prompt, model)
            return ProviderResult(
                raw_text=raw,
                provider=provider,
                model_name=model,
                latency_ms=_elapsed_ms(started),
            )
        if provider == "ollama":
            raw = ollama_client.generate_non_stream(
                prompt,
                model=model,
                json_format=json_format,
                timeout=timeout_sec,
            )
            return ProviderResult(
                raw_text=raw,
                provider=provider,
                model_name=model,
                latency_ms=_elapsed_ms(started),
            )
        if provider == "openai":
            raw, telemetry = openai_chat_json(
                prompt,
                model=model,
                timeout=timeout_sec,
            )
            if raw is None:
                return ProviderResult(
                    raw_text="",
                    provider=provider,
                    model_name=model,
                    latency_ms=_elapsed_ms(started),
                    error=str(telemetry.get("error") or "OpenAI call returned no content."),
                    telemetry=telemetry,
                )
            return ProviderResult(
                raw_text=raw,
                provider=provider,
                model_name=str(telemetry.get("model") or model),
                latency_ms=_elapsed_ms(started),
                telemetry=telemetry,
            )
        raise ValueError(f"Unsupported LLM provider: {provider}.")
    except Exception as exc:
        return ProviderResult(
            raw_text="",
            provider=provider,
            model_name=model,
            latency_ms=_elapsed_ms(started),
            error=str(exc),
        )


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))
