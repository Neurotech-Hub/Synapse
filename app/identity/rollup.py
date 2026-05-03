"""Organization / Place persona rollup (member snapshots + thin source excerpts)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from app.domain.effective_sources import source_ids_for_organization
from app.extensions import db
from app.identity.builder import IDENTITY_PROMPT_VERSION, apply_parsed_persona_payload
from app.identity.prompt import build_organization_persona_prompt, build_place_persona_prompt
from app.ingest.html_extract import plaintext_excerpt as _plaintext_excerpt
from app.ingest.ollama_client import OLLAMA_MODEL, run_identity_llm
from app.models import ContentItem, Organization, Person, PersonaSnapshot, Place


def _persona_mini_dict(sn: PersonaSnapshot | None) -> dict[str, Any]:
    if sn is None:
        return {}
    return {
        "research_focus": sn.research_focus or [],
        "methods": sn.methods or [],
        "keywords": sn.keywords or [],
        "current_projects": sn.current_projects or [],
        "funding_signals": sn.funding_signals or [],
        "collab_openness_score": sn.collab_openness_score,
        "notes": sn.notes or "",
    }


def _thin_excerpts_for_org(organization_id: int, *, cap_items: int = 24, excerpt_chars: int = 800) -> str:
    sids = source_ids_for_organization(int(organization_id))
    if not sids:
        return "(none)"
    cids = (
        ContentItem.query.filter(ContentItem.source_id.in_(sids))
        .order_by(desc(ContentItem.first_seen_at))
        .limit(cap_items)
        .all()
    )
    blocks: list[str] = []
    for ci in cids:
        tit = (ci.title or "").strip()
        sn = _plaintext_excerpt(ci.snippet or "", excerpt_chars).strip()
        blocks.append(f"title={tit}\nexcerpt={sn}")
    return "\n---\n".join(blocks) if blocks else "(none)"


def rebuild_organization_persona(
    organization_id: int,
    *,
    skip_if_same_fingerprint: bool = False,
    user_initiated: bool = False,
) -> dict[str, Any]:
    outcome: dict[str, Any] = {"organization_id": organization_id, "status": "skipped", "detail": ""}
    org = db.session.get(Organization, organization_id)
    if org is None:
        outcome["detail"] = "missing organization"
        return outcome

    members = Person.query.join(Person.organizations).filter(Organization.id == org.id).distinct().all()
    member_payload: list[dict[str, Any]] = []
    for p in members:
        sn = p.persona
        if sn is None or sn.build_status != "ok":
            continue
        d = _persona_mini_dict(sn)
        d["person_slug"] = p.slug
        d["person_name"] = p.display_name
        member_payload.append(d)

    excerpts = _thin_excerpts_for_org(org.id)
    rollup_fp_src = json.dumps(member_payload, ensure_ascii=False, sort_keys=True) + "\n|\n" + excerpts
    from hashlib import sha256

    fp = sha256(rollup_fp_src.encode()).hexdigest()[:64]

    row = org.persona
    if row is None:
        row = PersonaSnapshot(organization_id=org.id)
        db.session.add(row)
        org.persona = row

    if skip_if_same_fingerprint and row.input_fingerprint == fp and row.build_status == "ok":
        outcome["detail"] = "unchanged fingerprint"
        return outcome

    if not member_payload and excerpts.strip() == "(none)":
        row.prompt_version = IDENTITY_PROMPT_VERSION
        row.input_fingerprint = fp
        row.build_status = "stale"
        row.build_error = "No member personas and no org-associated source excerpts."
        row.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        outcome["status"] = "empty"
        outcome["detail"] = row.build_error or ""
        return outcome

    org_blob = (
        f"id={org.id}\nslug={org.slug}\ndisplay_name={org.display_name}\n"
        f"notes={(org.notes or '').strip()[:4000]}\npeople_count={len(members)}\n"
    )
    mp_json = json.dumps(member_payload, ensure_ascii=False)
    prompt = build_organization_persona_prompt(
        organization_blob=org_blob,
        member_personas_json=mp_json,
        source_excerpts=excerpts,
    )
    gen_at = datetime.now(timezone.utc)
    parsed, raw_model_text = run_identity_llm(prompt)
    if not isinstance(parsed, dict):
        if user_initiated:
            row.prompt_version = IDENTITY_PROMPT_VERSION
            row.input_fingerprint = fp
            row.build_status = "failed"
            snippet = " ".join((raw_model_text or "").split())
            snippet = snippet[:600] + ("…" if len(snippet) > 600 else "")
            row.build_error = "Model returned no usable JSON." + (
                f" Raw output (truncated): {snippet}" if snippet else ""
            )
            row.updated_at = gen_at
            row.model_used = OLLAMA_MODEL
            db.session.commit()
            outcome["status"] = "failed"
            outcome["detail"] = row.build_error or ""
            return outcome
        if row.build_status == "ok":
            row.updated_at = gen_at
            db.session.commit()
            outcome["detail"] = "LLM produced no JSON; previous persona kept."
            return outcome
        row.prompt_version = IDENTITY_PROMPT_VERSION
        row.input_fingerprint = fp
        row.build_status = "stale"
        row.updated_at = gen_at
        row.model_used = None
        db.session.commit()
        return outcome

    row.prompt_version = IDENTITY_PROMPT_VERSION
    row.input_fingerprint = fp
    apply_parsed_persona_payload(row, parsed)
    row.paper_count_last_90d = 0
    row.raw_papers_snapshot = []
    row.sources_last_scanned = {}
    row.build_status = "ok"
    row.build_error = None
    row.generated_at = gen_at
    row.model_used = OLLAMA_MODEL
    row.updated_at = gen_at
    db.session.commit()
    outcome["status"] = "ok"
    return outcome


def rebuild_place_persona(
    place_id: int,
    *,
    skip_if_same_fingerprint: bool = False,
    user_initiated: bool = False,
) -> dict[str, Any]:
    outcome: dict[str, Any] = {"place_id": place_id, "status": "skipped", "detail": ""}
    pl = (
        Place.query.options(joinedload(Place.organizations))
        .filter_by(id=int(place_id))
        .first()
    )
    if pl is None:
        outcome["detail"] = "missing place"
        return outcome

    org_ids_linked = sorted([o.id for o in (pl.organizations or [])])
    member_payload: list[dict[str, Any]] = []
    seen_pids: set[int] = set()
    for oid in org_ids_linked:
        memb = Person.query.join(Person.organizations).filter(Organization.id == oid).distinct().all()
        for p in memb:
            if p.id in seen_pids:
                continue
            seen_pids.add(p.id)
            sn = p.persona
            if sn is None or sn.build_status != "ok":
                continue
            d = _persona_mini_dict(sn)
            d["person_slug"] = p.slug
            member_payload.append(d)

    excerpt_cap = int(os.environ.get("SYNAPSE_PLACE_EXCERPT_CAP", "12"))
    per_org = max(4, excerpt_cap // max(1, len(org_ids_linked)))
    excerpt_segments = []
    for oid in org_ids_linked:
        seg = _thin_excerpts_for_org(oid, cap_items=per_org)
        if seg.strip() and seg.strip() != "(none)":
            excerpt_segments.append(seg)
    excerpts = "\n---\n".join(excerpt_segments).strip() if excerpt_segments else "(none)"
    rollup_fp_src = (
        json.dumps(member_payload, ensure_ascii=False, sort_keys=True)
        + repr((pl.latitude, pl.longitude))
        + repr(tuple(org_ids_linked))
    )
    from hashlib import sha256

    fp = sha256(rollup_fp_src.encode()).hexdigest()[:64]

    row = pl.persona
    if row is None:
        row = PersonaSnapshot(place_id=pl.id)
        db.session.add(row)
        pl.persona = row

    if skip_if_same_fingerprint and row.input_fingerprint == fp and row.build_status == "ok":
        outcome["detail"] = "unchanged fingerprint"
        return outcome

    org_blob_lines: list[str] = []
    for org in sorted(pl.organizations or [], key=lambda x: x.id):
        org_blob_lines.append(
            f"organization_id={org.id}\norganization_slug={org.slug}\n"
            f"organization_name={(org.display_name or '').strip()}\n---\n"
        )
    place_blob = (
        f"id={pl.id}\nslug={pl.slug}\ndisplay_name={pl.display_name}\n"
        f"place_name={pl.place_name}\nlatitude={pl.latitude}\nlongitude={pl.longitude}\n"
        f"{''.join(org_blob_lines)}notes={(pl.notes or '').strip()[:2000]}"
    )
    mp_json = json.dumps(member_payload, ensure_ascii=False)
    prompt = build_place_persona_prompt(
        place_blob=place_blob,
        member_personas_json=mp_json,
        source_excerpts=excerpts,
    )
    gen_at = datetime.now(timezone.utc)
    parsed, raw_model_text = run_identity_llm(prompt)
    if not isinstance(parsed, dict):
        if user_initiated:
            row.prompt_version = IDENTITY_PROMPT_VERSION
            row.input_fingerprint = fp
            row.build_status = "failed"
            snippet = " ".join((raw_model_text or "").split())
            snippet = snippet[:600] + ("…" if len(snippet) > 600 else "")
            row.build_error = "Model returned no usable JSON." + (
                f" Raw output (truncated): {snippet}" if snippet else ""
            )
            row.updated_at = gen_at
            row.model_used = OLLAMA_MODEL
            db.session.commit()
            outcome["status"] = "failed"
            outcome["detail"] = row.build_error or ""
            return outcome
        if row.build_status == "ok":
            row.updated_at = gen_at
            db.session.commit()
            outcome["detail"] = "LLM produced no JSON; previous persona kept."
            return outcome
        row.prompt_version = IDENTITY_PROMPT_VERSION
        row.input_fingerprint = fp
        row.build_status = "stale"
        row.updated_at = gen_at
        db.session.commit()
        return outcome

    row.prompt_version = IDENTITY_PROMPT_VERSION
    row.input_fingerprint = fp
    apply_parsed_persona_payload(row, parsed)
    row.paper_count_last_90d = 0
    row.raw_papers_snapshot = []
    row.sources_last_scanned = {}
    row.build_status = "ok"
    row.build_error = None
    row.generated_at = gen_at
    row.model_used = OLLAMA_MODEL
    row.updated_at = gen_at
    db.session.commit()
    outcome["status"] = "ok"
    return outcome
