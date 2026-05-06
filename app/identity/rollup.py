"""Organization / building persona rollup (member snapshots + thin source excerpts)."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from app.domain.effective_sources import identity_eligible_source_ids_for_organization
from app.domain.entity_associations import organization_ids_for_building
from app.extensions import db
from app.identity.builder import IDENTITY_PROMPT_VERSION, apply_parsed_persona_payload
from app.identity.prompt import build_organization_persona_prompt, build_place_persona_prompt
from app.identity.rebuild_modes import (
    default_manual_rebuild_mode,
    poll_persona_rebuild_mode,
)
from app.ingest.html_extract import plaintext_excerpt as _plaintext_excerpt
from app.ingest.llm_client import identity_llm_model_label, run_identity_llm
from app.models import Building, ContentItem, Organization, Person, PersonaSnapshot, Source


def _persona_json_str(sn: PersonaSnapshot | None) -> str | None:
    if sn is None:
        return None
    d = _persona_mini_dict(sn)
    raw = json.dumps(d, ensure_ascii=False, indent=2)
    return raw[:14_000]


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
        "hardware_interests": sn.hardware_interests or [],
        "infrastructure_needs": sn.infrastructure_needs or [],
        "notes": sn.notes or "",
    }


def sync_hub_persona_from_file(org: Organization) -> dict[str, Any]:
    """Populate PersonaSnapshot for the hub org from hub_persona.json (no LLM call)."""

    from app.leads.hub_corpus import load_hub_persona

    hp = load_hub_persona()
    caps = hp.get("capabilities", {})

    research_focus = [domain_data.get("summary", key) for key, domain_data in caps.items()]

    methods: list[str] = []
    for domain_data in caps.values():
        for cap in domain_data.get("capabilities", [])[:2]:
            if cap not in methods:
                methods.append(cap)
    methods = methods[:16]

    current_projects = [pp["name"] for pp in hp.get("proof_points", [])[:8]]
    keywords = hp.get("voice", {}).get("use_vocabulary", [])[:12]

    entity = hp.get("entity", {})
    mission = hp.get("mission", {})
    notes_raw = f"{entity.get('short_positioning', '')} {mission.get('summary', '')}".strip()
    notes = notes_raw[:600]

    hardware_interests: list[str] = []
    for domain in ("electronics_and_pcb", "embedded_systems", "bio_clinical_translational"):
        for ex in caps.get(domain, {}).get("example_use_cases", [])[:3]:
            if ex not in hardware_interests:
                hardware_interests.append(ex)
    hardware_interests = hardware_interests[:8]

    sw_cloud = caps.get("software_apps_cloud", {})
    infrastructure_needs = sw_cloud.get("capabilities", [])[:6]

    gen_at = datetime.now(timezone.utc)
    row = org.persona
    if row is None:
        row = PersonaSnapshot(organization_id=org.id)
        db.session.add(row)
        org.persona = row

    row.research_focus = research_focus
    row.methods = methods
    row.keywords = keywords
    row.current_projects = current_projects
    row.funding_signals = []
    row.collab_openness_score = 1.0
    row.hardware_interests = hardware_interests
    row.infrastructure_needs = infrastructure_needs
    row.notes = notes
    row.paper_count_last_90d = 0
    row.raw_papers_snapshot = []
    row.sources_last_scanned = {}
    row.build_status = "ok"
    row.build_error = None
    row.generated_at = gen_at
    row.model_used = "hub_persona.json"
    row.prompt_version = IDENTITY_PROMPT_VERSION
    row.input_fingerprint = hp.get("schema_version", "1.0")
    row.updated_at = gen_at
    db.session.commit()
    return {"organization_id": org.id, "status": "ok", "detail": "synced from hub_persona.json"}


def _content_item_excerpt_line(ci: ContentItem, excerpt_chars: int) -> str:
    """Single labeled block for one ContentItem, including source kind and URL."""
    src = ci.source
    src_kind = (src.kind if src else "") or "unknown"
    src_url = (src.url if src else "") or ""
    tit = (ci.title or "").strip()
    sn = _plaintext_excerpt(ci.snippet or "", excerpt_chars).strip()
    return f"SOURCE_KIND={src_kind}\nSOURCE_URL={src_url}\ntitle={tit}\nexcerpt={sn}"


def _content_item_excerpt_lines(items: Iterable[ContentItem], excerpt_chars: int) -> list[str]:
    return [_content_item_excerpt_line(ci, excerpt_chars) for ci in items]


def _thin_excerpts_for_org(organization_id: int, *, cap_items: int = 24, excerpt_chars: int = 800) -> str:
    """Feed org-owned source content as primary evidence; member RSS as fallback only."""

    oid = int(organization_id)
    eligible = identity_eligible_source_ids_for_organization(oid)
    if not eligible:
        return "(none)"

    org_owned_rows = (
        Source.query.with_entities(Source.id, Source.kind)
        .filter(Source.organization_id == oid, Source.id.in_(eligible))
        .order_by(Source.id.asc())
        .all()
    )
    org_owned_ids = [int(r[0]) for r in org_owned_rows]
    org_owned_kinds = {int(r[0]): r[1] for r in org_owned_rows}
    org_set = set(org_owned_ids)
    member_ids = [sid for sid in eligible if sid not in org_set]

    if org_owned_ids:
        # Give HTML sources a much larger character budget — they carry full page text that defines
        # mission and scope. RSS items on the org get the standard budget.
        has_html = any(k == "html_page" for k in org_owned_kinds.values())
        html_chars = 3000
        rss_chars = max(excerpt_chars, 800)

        org_items = (
            ContentItem.query.filter(ContentItem.source_id.in_(org_owned_ids))
            .options(joinedload(ContentItem.source))
            .order_by(desc(ContentItem.first_seen_at))
            .limit(cap_items)
            .all()
        )
        org_lines: list[str] = []
        for ci in org_items:
            src_kind = (ci.source.kind if ci.source else "") or "unknown"
            chars = html_chars if src_kind == "html_page" else rss_chars
            org_lines.append(_content_item_excerpt_line(ci, chars))

        # When org-owned sources exist, member excerpts are omitted entirely: the member persona
        # JSON blob is already passed to the prompt and is the correct vehicle for that information.
        parts: list[str] = []
        if org_lines:
            parts.append("OFFICIAL_ORG_SOURCES\n" + "\n---\n".join(org_lines))
        return "\n\n".join(parts) if parts else "(none)"

    # No org-owned sources — fall back to member-affiliated RSS excerpts.
    cids = (
        ContentItem.query.filter(ContentItem.source_id.in_(eligible))
        .options(joinedload(ContentItem.source))
        .order_by(desc(ContentItem.first_seen_at))
        .limit(cap_items)
        .all()
    )
    mem_only = _content_item_excerpt_lines(cids, excerpt_chars)
    if not mem_only:
        return "(none)"
    return "MEMBER_AFFILIATED_SOURCES\n" + "\n---\n".join(mem_only)


def rebuild_organization_persona(
    organization_id: int,
    *,
    skip_if_same_fingerprint: bool = False,
    user_initiated: bool = False,
    rebuild_mode: str | None = None,
) -> dict[str, Any]:
    outcome: dict[str, Any] = {"organization_id": organization_id, "status": "skipped", "detail": ""}
    org = db.session.get(Organization, organization_id)
    if org is None:
        outcome["detail"] = "missing organization"
        return outcome

    if getattr(org, "is_hub", False):
        return sync_hub_persona_from_file(org)

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

    eligible_source_ids = identity_eligible_source_ids_for_organization(org.id)
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

    mode_raw = rebuild_mode
    if mode_raw is None:
        mode_raw = default_manual_rebuild_mode() if user_initiated else poll_persona_rebuild_mode()
    eff_mode = (mode_raw or "full").strip().lower()
    if eff_mode not in ("full", "incremental", "light_refresh"):
        eff_mode = "full"
    if eff_mode in ("incremental", "light_refresh") and (row.build_status != "ok" or not row.generated_at):
        eff_mode = "full"
    prev_org_json = _persona_json_str(row) if eff_mode in ("incremental", "light_refresh") else None

    if not member_payload and excerpts.strip() == "(none)":
        if eligible_source_ids:
            msg = "Org has attached sources, but no ingested content yet. Run Poll now to fetch source content first."
        else:
            msg = "No member personas and no org-associated source excerpts."
        row.prompt_version = IDENTITY_PROMPT_VERSION
        row.input_fingerprint = fp
        row.build_status = "stale"
        row.build_error = msg
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
        rebuild_mode=eff_mode,
        previous_persona_json=prev_org_json,
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
            row.model_used = identity_llm_model_label()
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
    row.model_used = identity_llm_model_label()
    row.updated_at = gen_at
    db.session.commit()
    outcome["status"] = "ok"
    return outcome


def rebuild_building_persona(
    building_id: int,
    *,
    skip_if_same_fingerprint: bool = False,
    user_initiated: bool = False,
    rebuild_mode: str | None = None,
) -> dict[str, Any]:
    outcome: dict[str, Any] = {"building_id": building_id, "status": "skipped", "detail": ""}
    pl = (
        Building.query.options(joinedload(Building.organizations))
        .filter_by(id=int(building_id))
        .first()
    )
    if pl is None:
        outcome["detail"] = "missing building"
        return outcome

    org_ids_linked = sorted(organization_ids_for_building(int(building_id)))
    org_objs = [db.session.get(Organization, oid) for oid in org_ids_linked]
    org_objs = [o for o in org_objs if o is not None]

    member_payload: list[dict[str, Any]] = []
    seen_pids: set[int] = set()
    for org in org_objs:
        memb = Person.query.join(Person.organizations).filter(Organization.id == org.id).distinct().all()
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
        + "\n|\n"
        + excerpts
    )
    from hashlib import sha256

    fp = sha256(rollup_fp_src.encode()).hexdigest()[:64]

    row = pl.persona
    if row is None:
        row = PersonaSnapshot(building_id=pl.id)
        db.session.add(row)
        pl.persona = row

    if skip_if_same_fingerprint and row.input_fingerprint == fp and row.build_status == "ok":
        outcome["detail"] = "unchanged fingerprint"
        return outcome

    mode_raw_b = rebuild_mode
    if mode_raw_b is None:
        mode_raw_b = default_manual_rebuild_mode() if user_initiated else poll_persona_rebuild_mode()
    eff_mode_b = (mode_raw_b or "full").strip().lower()
    if eff_mode_b not in ("full", "incremental", "light_refresh"):
        eff_mode_b = "full"
    if eff_mode_b in ("incremental", "light_refresh") and (row.build_status != "ok" or not row.generated_at):
        eff_mode_b = "full"
    prev_place_json = _persona_json_str(row) if eff_mode_b in ("incremental", "light_refresh") else None

    org_blob_lines: list[str] = []
    for org in sorted(org_objs, key=lambda x: x.id):
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
        rebuild_mode=eff_mode_b,
        previous_persona_json=prev_place_json,
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
            row.model_used = identity_llm_model_label()
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
    row.model_used = identity_llm_model_label()
    row.updated_at = gen_at
    db.session.commit()
    outcome["status"] = "ok"
    return outcome
