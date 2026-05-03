"""Shared helpers for loading prompt text from the repo ``prompts/`` directory."""

from __future__ import annotations

from pathlib import Path


def prompts_dir() -> Path:
    """``prompts/`` at repo root."""

    return Path(__file__).resolve().parent.parent.parent / "prompts"


def normalize_prompt_body(text: str | None) -> str:
    """Normalize newlines and outer whitespace for equality checks."""

    if text is None:
        return ""
    return "\n".join(text.replace("\r\n", "\n").splitlines()).strip()
