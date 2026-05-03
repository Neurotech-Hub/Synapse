"""Load editable qualification prompts from DB override or repo ``prompts/``."""

from __future__ import annotations

from pathlib import Path

from app.extensions import db
from app.models import LeadPipelineSettings


def prompts_dir() -> Path:
    # app/leads → app → Synapse repo root
    return Path(__file__).resolve().parent.parent.parent / "prompts"


def load_default_qualified_lead_template() -> str:
    """Bundled ``prompts/qualified_lead.txt`` (no DB)."""
    path = prompts_dir() / "qualified_lead.txt"
    return path.read_text(encoding="utf-8")


def normalize_prompt_body(text: str | None) -> str:
    """Normalize newlines and outer whitespace for equality checks."""
    if text is None:
        return ""
    return "\n".join(text.replace("\r\n", "\n").splitlines()).strip()


def load_qualified_lead_template() -> str:
    """Effective template: DB override on ``lead_pipeline_settings`` when non-empty, else file."""
    row = db.session.get(LeadPipelineSettings, 1)
    if row is not None and row.qualified_lead_prompt_body is not None:
        raw = row.qualified_lead_prompt_body
        if raw.strip():
            return raw
    return load_default_qualified_lead_template()


def build_qualified_lead_prompt(
    *,
    hub_context: str,
    candidate: str,
    entity_catalog: str,
) -> str:
    t = load_qualified_lead_template()
    return (
        t.replace("{{hub_context}}", hub_context)
        .replace("{{candidate}}", candidate)
        .replace("{{entity_catalog}}", entity_catalog)
    )
