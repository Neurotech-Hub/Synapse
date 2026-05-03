"""Caps for Hub-centric lead reports (prefer large evidence over persona-only glimpses).

Defaults are conservative for cost; ops can bump via SYNAPSE_LEAD_REPORT_* env when needed."""

from __future__ import annotations

import os


def _env_int(key: str, default: int, floor: int, ceiling: int) -> int:
    raw = (os.environ.get(key) or "").strip()
    if not raw:
        return default
    try:
        return max(floor, min(ceiling, int(raw)))
    except ValueError:
        return default


# How many Hub content items to concatenate (recent first): analog to legacy "max hub snippets".
def hub_items_max_default() -> int:
    return _env_int("SYNAPSE_LEAD_REPORT_HUB_ITEMS_MAX", 30, 4, 200)


def hub_snippet_chars_default() -> int:
    """Per-Hub-item snippet truncation in report prompts (characters)."""
    return _env_int("SYNAPSE_LEAD_REPORT_HUB_SNIPPET_CHARS", 24_000, 4_096, 64_000)


def person_owned_items_max() -> int:
    return _env_int("SYNAPSE_LEAD_REPORT_PERSON_ITEMS_MAX", 80, 8, 500)


def person_content_budget_chars() -> int:
    """Total approximate budget for concatenated owned-source evidence for a target person."""
    return _env_int("SYNAPSE_LEAD_REPORT_PERSON_CONTENT_CHARS", 90_000, 16_000, 280_000)


def org_place_persona_summaries_cap() -> int:
    """Max affiliated people enumerated with persona stubs (org / place rollup)."""
    return _env_int("SYNAPSE_LEAD_REPORT_ORG_PEOPLE_MAX", 40, 4, 200)


# Pipeline semver for input_fingerprint bumps when prompt/evidence semantics change materially.
PIPELINE_SEMVER = os.environ.get("SYNAPSE_LEAD_REPORT_PIPELINE_SEMVER", "1").strip() or "1"
