"""Rebuild ``PersonaSnapshot`` for persons, organizations, and buildings via local Ollama."""

from __future__ import annotations

import os
import traceback
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.identity.evidence import (
    batch_summary_for_prompt,
    chunks_for_prompt,
    content_fingerprint,
    gather_content_items_for_person,
    identity_paper_overlay_days,
    paper_count_for_owned_sources,
    raw_papers_snapshot,
    sources_last_scanned_for_person,
)
from app.identity.prompt import build_person_identity_prompt
from app.ingest.ollama_client import OLLAMA_MODEL, run_identity_llm
from app.models import Person, PersonaSnapshot, Source

IDENTITY_PROMPT_VERSION = (os.environ.get("SYNAPSE_IDENTITY_PROMPT_VERSION") or "1").strip() or "1"


def _as_str_list(raw: Any) -> list[str]:
    if raw is None or not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        s = str(x).strip()
        if s:
            out.append(s[:1200])
    return out[:64]


def _as_float(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, v))


def apply_parsed_persona_payload(row: PersonaSnapshot, parsed: dict[str, Any]) -> None:
    row.research_focus = _as_str_list(parsed.get("research_focus"))
    row.methods = _as_str_list(parsed.get("methods"))
    row.keywords = _as_str_list(parsed.get("keywords"))
    row.current_projects = _as_str_list(parsed.get("current_projects"))
    row.funding_signals = _as_str_list(parsed.get("funding_signals"))
    row.collab_openness_score = _as_float(parsed.get("collab_openness_score"))
    row.hardware_interests = _as_str_list(parsed.get("hardware_interests"))
    row.infrastructure_needs = _as_str_list(parsed.get("infrastructure_needs"))
    row.notes = (str(parsed.get("notes") or "").strip()[:8000] or None)


def person_ids_for_owned_sources(source_ids: list[int]) -> list[int]:
    if not source_ids:
        return []
    rows = (
        Source.query.with_entities(Source.person_id)
        .filter(Source.id.in_(source_ids), Source.person_id.isnot(None))
        .distinct()
        .all()
    )
    return sorted({int(r[0]) for r in rows if r[0] is not None})


def rebuild_person_identity(
    person_id: int,
    *,
    skip_if_same_fingerprint: bool = False,
    user_initiated: bool = False,
) -> dict[str, Any]:
    """Run identity job for ``person_id``. Returns outcome dict."""

    outcome: dict[str, Any] = {"person_id": person_id, "status": "skipped", "detail": ""}
    ent = (
        Person.query.options(joinedload(Person.organizations))
        .filter_by(id=int(person_id))
        .first()
    )
    if ent is None:
        outcome["detail"] = "not a person row"
        return outcome

    items = gather_content_items_for_person(ent, limit=int(os.environ.get("SYNAPSE_IDENTITY_MAX_ITEMS", "80")))
    fp = content_fingerprint(items)
    overlay_papers = paper_count_for_owned_sources(ent, days=identity_paper_overlay_days())
    overlay_snapshot = raw_papers_snapshot(items, cap=int(os.environ.get("SYNAPSE_IDENTITY_SNAPSHOT_CAP", "40")))
    overlay_scanned = sources_last_scanned_for_person(ent)
    gen_at = datetime.now(timezone.utc)

    row = ent.persona
    if row is None:
        row = PersonaSnapshot(person_id=ent.id)
        db.session.add(row)
        ent.persona = row

    if skip_if_same_fingerprint and row.input_fingerprint == fp and row.build_status == "ok":
        outcome["detail"] = "unchanged fingerprint"
        return outcome

    if not items:
        row.prompt_version = IDENTITY_PROMPT_VERSION
        row.input_fingerprint = fp
        row.build_status = "stale"
        row.build_error = "No owned ingest evidence — assign this person as owner on approved sources."
        row.paper_count_last_90d = 0
        row.raw_papers_snapshot = []
        row.sources_last_scanned = overlay_scanned
        row.updated_at = gen_at
        row.generated_at = None
        row.model_used = None
        db.session.commit()
        outcome["status"] = "empty"
        outcome["detail"] = row.build_error or ""
        return outcome

    org_blob = ""
    for org in sorted(getattr(ent, "organizations", None) or [], key=lambda x: x.id):
        org_blob += (
            f"organization_id={org.id}\norganization_slug={org.slug}\n"
            f"organization_name={(org.display_name or '').strip()}\n---\n"
        )

    person_blob = (
        f"id={ent.id}\nslug={ent.slug}\nname={ent.display_name}\n"
        f"{org_blob}"
        f"manual_notes={(ent.notes or '').strip()[:2000]}"
    )

    try:
        batch_threshold = max(1, int(os.environ.get("SYNAPSE_IDENTITY_FULL_BATCH_THRESHOLD", "30")))
    except ValueError:
        batch_threshold = 30

    if len(items) > batch_threshold:
        detail_items = items[:batch_threshold]
        tail_items = items[batch_threshold:]
        detail_chunks = chunks_for_prompt(detail_items)
        tail_summary = batch_summary_for_prompt(tail_items)
        content_chunks = detail_chunks
        if tail_summary:
            content_chunks += "\n\n---\n\nBATCH_SUMMARY_OF_OLDER_ITEMS:\n" + tail_summary
    else:
        content_chunks = chunks_for_prompt(items)

    prompt = build_person_identity_prompt(person_blob=person_blob, content_chunks=content_chunks)
    parsed, raw_model_text = run_identity_llm(prompt)
    if not isinstance(parsed, dict):
        if user_initiated:
            row.prompt_version = IDENTITY_PROMPT_VERSION
            row.input_fingerprint = fp
            row.build_status = "failed"
            snippet = " ".join((raw_model_text or "").split())
            snippet = snippet[:600] + ("…" if len(snippet) > 600 else "")
            row.build_error = (
                "Model returned no usable JSON." + (f" Raw output (truncated): {snippet}" if snippet else "")
            )
            row.paper_count_last_90d = overlay_papers
            row.raw_papers_snapshot = overlay_snapshot
            row.sources_last_scanned = overlay_scanned
            row.updated_at = gen_at
            row.model_used = OLLAMA_MODEL
            db.session.commit()
            outcome["status"] = "failed"
            outcome["detail"] = row.build_error or ""
            return outcome
        if row.build_status == "ok":
            row.paper_count_last_90d = overlay_papers
            row.raw_papers_snapshot = overlay_snapshot
            row.sources_last_scanned = overlay_scanned
            row.updated_at = gen_at
            db.session.commit()
            outcome["detail"] = "LLM produced no JSON; previous persona kept."
            return outcome
        row.prompt_version = IDENTITY_PROMPT_VERSION
        row.input_fingerprint = fp
        row.build_status = "stale"
        row.build_error = None
        row.paper_count_last_90d = overlay_papers
        row.raw_papers_snapshot = overlay_snapshot
        row.sources_last_scanned = overlay_scanned
        row.updated_at = gen_at
        row.generated_at = None
        row.model_used = None
        db.session.commit()
        outcome["detail"] = ""
        return outcome

    row.prompt_version = IDENTITY_PROMPT_VERSION
    row.input_fingerprint = fp
    apply_parsed_persona_payload(row, parsed)
    row.paper_count_last_90d = overlay_papers
    row.raw_papers_snapshot = overlay_snapshot
    row.sources_last_scanned = overlay_scanned
    row.build_status = "ok"
    row.build_error = None
    row.generated_at = gen_at
    row.model_used = OLLAMA_MODEL
    row.updated_at = gen_at
    db.session.commit()
    outcome["status"] = "ok"
    return outcome


def rebuild_person_identities_bounded(source_ids: list[int], *, max_entities: int = 6) -> list[dict[str, Any]]:
    """After poll/save touched sources — refresh personas for owners (budgeted burst)."""

    pids = person_ids_for_owned_sources(source_ids)
    out: list[dict[str, Any]] = []
    for pid in sorted(pids)[: max(0, int(max_entities))]:
        try:
            out.append(rebuild_person_identity(pid, skip_if_same_fingerprint=True))
        except Exception:
            out.append({"person_id": pid, "status": "skipped", "detail": traceback.format_exc()[-800:]})
    return out
