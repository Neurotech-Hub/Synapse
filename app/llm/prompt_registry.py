from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PromptSpec:
    name: str
    path: str
    version: str
    default_provider: str
    fallback_provider: str | None
    output: str
    max_input_chars: int | None = None
    public_safe: bool = False
    private_internal: bool = False


PROMPTS: dict[str, PromptSpec] = {
    "funding_extract": PromptSpec("funding_extract", "prompts/funding_extract.txt", "1.0.0", "ollama", "openai", "json", 24_000),
    "funding_effort_classify": PromptSpec("funding_effort_classify", "prompts/funding_effort_classify.txt", "1.0.0", "ollama", "openai", "json", 8_000),
    "funding_public_card": PromptSpec("funding_public_card", "prompts/funding_public_card.txt", "1.0.0", "ollama", "openai", "json", 6_000, public_safe=True),
    "public_entity_summary": PromptSpec("public_entity_summary", "prompts/public_entity_summary.txt", "1.0.0", "ollama", "openai", "json", public_safe=True),
    "public_place_summary": PromptSpec("public_place_summary", "prompts/public_place_summary.txt", "1.0.0", "ollama", "openai", "json", public_safe=True),
    "json_repair": PromptSpec("json_repair", "prompts/json_repair.txt", "1.0.0", "ollama", "openai", "json"),
}

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def prompts_dir() -> Path:
    return repo_root() / "prompts"


def get_prompt_spec(name: str) -> PromptSpec:
    try:
        return PROMPTS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown prompt: {name}") from exc


def load_prompt_template(name: str) -> str:
    spec = get_prompt_spec(name)
    path = repo_root() / spec.path
    if not path.exists():
        raise FileNotFoundError(f"Prompt file missing for {name}: {path}")
    return path.read_text(encoding="utf-8")


def prompt_placeholders(name: str) -> set[str]:
    return set(_PLACEHOLDER_RE.findall(load_prompt_template(name)))


def render_prompt(name: str, variables: dict[str, Any]) -> str:
    template = load_prompt_template(name)
    rendered = template
    missing: list[str] = []
    for placeholder in sorted(set(_PLACEHOLDER_RE.findall(template))):
        if placeholder not in variables:
            missing.append(placeholder)
            continue
        rendered = re.sub(r"\{\{\s*" + re.escape(placeholder) + r"\s*\}\}", _stringify(variables[placeholder]), rendered)
    if missing:
        raise KeyError(f"Missing prompt variable(s) for {name}: {', '.join(missing)}")
    return rendered


def prompt_input_fingerprint(name: str, variables: dict[str, Any]) -> str:
    spec = get_prompt_spec(name)
    payload = {
        "name": spec.name,
        "version": spec.version,
        "variables": variables,
    }
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def effective_prompt_provider(name: str) -> str:
    spec = get_prompt_spec(name)
    env_name = "SYNAPSE_LLM_" + name.upper() + "_PROVIDER"
    raw = (os.environ.get(env_name) or "").strip().lower()
    if raw in {"ollama", "openai", "auto"}:
        return raw
    return spec.default_provider


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, indent=2, default=str)
