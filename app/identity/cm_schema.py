"""Connection-maker-aligned persona JSON contract (parity with persona.py REQUIRED_FIELDS)."""

from __future__ import annotations

REQUIRED_FIELDS = frozenset(
    {
        "research_focus",
        "methods",
        "keywords",
        "current_projects",
        "funding_signals",
        "collab_openness_score",
        "notes",
    }
)
