"""Hub-side source IDs and hub_persona.json loading for reports and personas."""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.effective_sources import source_ids_for_organization
from app.extensions import db
from app.models import Source

_HUB_PERSONA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "hub_persona.json"


def load_hub_persona() -> dict:
    """Load data/hub_persona.json. Raises FileNotFoundError with a clear message if missing."""
    if not _HUB_PERSONA_PATH.exists():
        raise FileNotFoundError(
            f"hub_persona.json not found at {_HUB_PERSONA_PATH}. "
            "Create data/hub_persona.json to enable hub-persona-driven lead reports."
        )
    return json.loads(_HUB_PERSONA_PATH.read_text(encoding="utf-8"))


def hub_persona_context_block() -> str:
    """Compact NTH identity + capability block for org/building lead report prompts."""
    hp = load_hub_persona()
    long_prompt = hp.get("long_agent_prompt", "")
    caps = hp.get("capabilities", {})
    cap_lines = [f"- {k}: {v.get('summary', '')}" for k, v in caps.items()]
    signals = hp.get("signals", {})
    ideal = signals.get("ideal_collaborator_signals", [])
    proof_pts = [pp["name"] for pp in hp.get("proof_points", [])[:6]]
    return (
        f"HUB AGENT CONTEXT:\n{long_prompt}\n\n"
        "CAPABILITIES:\n" + "\n".join(cap_lines) + "\n\n"
        "IDEAL COLLABORATOR SIGNALS:\n" + "\n".join(f"- {s}" for s in ideal[:10]) + "\n\n"
        f"KEY PROOF POINTS: {', '.join(proof_pts)}"
    )


def hub_source_ids(*, hub_organization_id: int | None) -> set[int]:
    """Sources whose owner (person or organization) belongs to the Hub corpus organization."""

    if hub_organization_id is None:
        return set()
    return source_ids_for_organization(int(hub_organization_id))


def hub_corpus_mark_person_ids(*, hub_organization_id: int | None) -> set[int]:
    """Person ids that own at least one qualifying Hub-corpus source."""

    sids = hub_source_ids(hub_organization_id=hub_organization_id)
    if not sids:
        return set()
    rows = (
        db.session.query(Source.person_id)
        .filter(Source.id.in_(sids), Source.person_id.isnot(None))
        .distinct()
        .all()
    )
    return {int(r[0]) for r in rows if r[0] is not None}


def hub_corpus_mark_organization_ids(*, hub_organization_id: int | None) -> set[int]:
    """Organization ids that own at least one qualifying Hub-corpus source."""

    sids = hub_source_ids(hub_organization_id=hub_organization_id)
    if not sids:
        return set()
    rows = (
        db.session.query(Source.organization_id)
        .filter(Source.id.in_(sids), Source.organization_id.isnot(None))
        .distinct()
        .all()
    )
    return {int(r[0]) for r in rows if r[0] is not None}
