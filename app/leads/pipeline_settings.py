"""Admin-persisted lead pipeline toggles and caps (singleton row ``id=1``)."""

from __future__ import annotations

from flask import current_app

from app.extensions import db
from app.models import LeadPipelineSettings


def get_singleton() -> LeadPipelineSettings:
    """Return the settings row, creating the singleton with sane defaults if missing."""

    row = db.session.get(LeadPipelineSettings, 1)
    if row is None:
        row = LeadPipelineSettings(
            id=1,
            qualify_enabled=bool(current_app.config.get("SYNAPSE_LEADS_QUALIFY")),
            prompt_version=str(current_app.config.get("SYNAPSE_LEADS_PROMPT_VERSION", "1")).strip() or "1",
            max_hub_items=_fallback_int("SYNAPSE_LEADS_MAX_HUB_ITEMS", 25),
            max_candidates_per_run=_fallback_int("SYNAPSE_LEADS_MAX_CANDIDATES_PER_RUN", 30),
            entity_catalog_max=_fallback_int("SYNAPSE_LEADS_ENTITY_CATALOG_MAX", 40),
        )
        db.session.add(row)
        db.session.commit()
    return row


def _fallback_int(env_key: str, default: int) -> int:
    try:
        return int(current_app.config.get(env_key, default))
    except (TypeError, ValueError):
        return default


def bump_prompt_version_tag(current: str) -> str:
    """Increment the stored prompt version when qualification prompt text changes.

    Numeric tags (e.g. ``9`` → ``10``). Non-numeric legacy tags bump to ``2`` so new leads dedupe cleanly.
    """

    s = (current or "").strip() or "1"
    if s.isdigit():
        return str(int(s) + 1)
    return "2"


def get_qualification_runtime_config() -> dict:
    """Values used by :func:`app.leads.qualification.run_lead_qualification`."""

    row = db.session.get(LeadPipelineSettings, 1)
    if row is None:
        return {
            "max_hub_items": _fallback_int("SYNAPSE_LEADS_MAX_HUB_ITEMS", 25),
            "max_candidates_per_run": _fallback_int("SYNAPSE_LEADS_MAX_CANDIDATES_PER_RUN", 30),
            "entity_catalog_max": _fallback_int("SYNAPSE_LEADS_ENTITY_CATALOG_MAX", 40),
            "prompt_version": str(current_app.config.get("SYNAPSE_LEADS_PROMPT_VERSION", "1")).strip() or "1",
            "qualify_enabled": bool(current_app.config.get("SYNAPSE_LEADS_QUALIFY")),
        }
    pv = (row.prompt_version or "").strip() or "1"
    return {
        "max_hub_items": row.max_hub_items,
        "max_candidates_per_run": row.max_candidates_per_run,
        "entity_catalog_max": row.entity_catalog_max,
        "prompt_version": pv,
        "qualify_enabled": bool(row.qualify_enabled),
    }
