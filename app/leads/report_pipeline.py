"""Multi-step Hub-centric lead report synthesis (person / organization / building / region)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.domain.entity_associations import organization_ids_for_building
from app.domain.region_buildings import building_ids_for_region, ensure_region_building_rows
from app.identity.evidence import gather_content_items_for_person, chunks_for_prompt
from app.ingest.html_extract import plaintext_excerpt as _plain_excerpt
from app.ingest.llm_client import lead_report_model_label, run_lead_report_llm
from app.leads.hub_corpus import hub_persona_context_block, load_hub_persona
from app.leads.lead_report_budgets import (
    PIPELINE_SEMVER,
    org_place_persona_summaries_cap,
    person_short_evidence_items,
)
from app.leads.prompt_loader import normalize_prompt_body, prompts_dir
from app.leads.report_progress import set_lead_report_phase
from app.models import (
    ContentItem,
    LeadReport,
    Organization,
    Person,
    PersonaSnapshot,
    person_organization,
)


def _report_snippet_block(ci: ContentItem, *, max_chars: int) -> str:
    body = _plain_excerpt((ci.snippet or ""), max_chars).strip()
    lk = ci.link or ""
    return (
        f"CONTENT_ITEM_ID={ci.id}\n"
        f"title={(ci.title or '').strip()}\n"
        f"link={lk}\n"
        f"snippet={body}"
    )


def _load_prompt_file(name: str) -> str:
    return (prompts_dir() / name).read_text(encoding="utf-8")


def _hub_items_and_block(*, hub_organization_id: int) -> tuple[list[ContentItem], str]:
    """Deprecated: hub context now comes from hub_persona.json, not ContentItems."""
    return [], ""


def _fingerprint_hub_target(
    *,
    hub_ids: list[int],
    target_person_id: int | None,
    target_organization_id: int | None,
    target_building_id: int | None,
    target_region_id: int | None,
) -> str:
    h_part = "|".join(str(i) for i in sorted(set(hub_ids)))
    subj = ""
    if target_person_id is not None:
        subj = f"person:{target_person_id}"
    elif target_organization_id is not None:
        subj = f"organization:{target_organization_id}"
    elif target_building_id is not None:
        subj = f"building:{target_building_id}"
    elif target_region_id is not None:
        subj = f"region:{target_region_id}"
    raw = f"{PIPELINE_SEMVER}|hub:[{h_part}]|tgt:{subj}"
    return sha256(raw.encode()).hexdigest()[:64]


def _person_target_block(person: Person) -> tuple[list[ContentItem], str, str]:
    """Short evidence window + full persona JSON (persona-first lead gen)."""

    items = gather_content_items_for_person(person, limit=int(person_short_evidence_items()))
    evidence_block = chunks_for_prompt(items)

    persona_json_str = "(no persona snapshot)"
    ps = PersonaSnapshot.query.filter_by(person_id=person.id).first()
    if ps and ps.build_status == "ok":
        persona_dict: dict[str, Any] = {
            "research_focus": ps.research_focus or [],
            "methods": ps.methods or [],
            "keywords": ps.keywords or [],
            "current_projects": ps.current_projects or [],
            "funding_signals": ps.funding_signals or [],
            "hardware_interests": ps.hardware_interests or [],
            "infrastructure_needs": ps.infrastructure_needs or [],
            "collab_openness_score": ps.collab_openness_score,
            "notes": ps.notes or "",
        }
        persona_json_str = json.dumps(persona_dict, ensure_ascii=False)

    return items, evidence_block, persona_json_str


def _sanitize_id_list(vals: Any, *, allowed: set[int]) -> list[int]:
    out: list[int] = []
    if not isinstance(vals, list):
        return out
    for x in vals:
        try:
            n = int(x)
        except (TypeError, ValueError):
            continue
        if n in allowed:
            out.append(n)
    return sorted(set(out))[:24]


def _normalize_routes(data: dict[str, Any], *, hub_ids: set[int], target_ids: set[int]) -> list[dict[str, Any]]:
    raw_list = data.get("collaboration_routes") or data.get("routes")
    if not isinstance(raw_list, list):
        return []
    out: list[dict[str, Any]] = []
    for obj in raw_list[:5]:
        if not isinstance(obj, dict):
            continue
        out.append(
            {
                "title": str(obj.get("title") or "").strip()[:512],
                "why": str(obj.get("why") or "").strip()[:12000],
                "next_step": str(obj.get("next_step") or "").strip()[:4000],
                "hub_evidence_refs": _sanitize_id_list(obj.get("hub_evidence_refs"), allowed=hub_ids),
                "target_evidence_refs": _sanitize_id_list(obj.get("target_evidence_refs"), allowed=target_ids),
            }
        )
    return [r for r in out if r.get("title") or r.get("why")]


def _organization_ids_for_report(report: LeadReport) -> tuple[list[int], str]:
    """Organizations whose people roster feeds org/building/region rollup."""

    if report.target_organization_id is not None:
        return [int(report.target_organization_id)], f"organization id={report.target_organization_id}"
    if report.target_building_id is not None:
        oids = sorted(organization_ids_for_building(int(report.target_building_id)))
        return oids, f"building id={report.target_building_id}"
    if report.target_region_id is not None:
        rid = int(report.target_region_id)
        ensure_region_building_rows(rid)
        oids: set[int] = set()
        for bid in building_ids_for_region(rid):
            oids |= organization_ids_for_building(int(bid))
        return sorted(oids), f"region id={rid}"
    return [], ""


def _people_roster_for_orgs(
    organization_ids: list[int], *, hub_organization_id: int | None
) -> tuple[list[Person], str]:
    """People in scope orgs, excluding anyone also affiliated with the Hub corpus org."""

    if not organization_ids:
        return [], "(No organizations in scope.)"

    q = (
        Person.query.join(person_organization)
        .filter(person_organization.c.organization_id.in_(organization_ids))
        .distinct()
    )
    if hub_organization_id is not None:
        hub_member_ids = select(person_organization.c.person_id).where(
            person_organization.c.organization_id == int(hub_organization_id)
        )
        q = q.filter(Person.id.not_in(hub_member_ids))
    q = q.order_by(Person.display_name.asc()).limit(org_place_persona_summaries_cap())
    people = q.all()

    lines = [_person_rich_stub(p.id) for p in people]
    return people, "\n".join(lines) if lines else "(no affiliated people captured.)"


def _person_rich_stub(person_id: int) -> str:
    """Rich persona stub for org/building lead report rosters."""
    p = db.session.get(Person, person_id)
    tag = "unknown"
    if p:
        tag = f'person id={p.id} slug="{p.slug}" display_name="{p.display_name}"'
    ps = PersonaSnapshot.query.filter_by(person_id=person_id).first()
    bits: list[str] = []
    if ps and ps.build_status == "ok":
        if isinstance(ps.research_focus, list):
            rf = "; ".join(str(x).strip() for x in ps.research_focus[:5] if str(x).strip())
            if rf:
                bits.append(f"research_focus=[{rf}]")
        if ps.collab_openness_score is not None:
            bits.append(f"collab_score={float(ps.collab_openness_score):.2f}")
        if isinstance(ps.keywords, list):
            kw = " ".join(str(x).strip() for x in ps.keywords[:8] if str(x).strip())
            if kw:
                bits.append(f"keywords={kw}")
        hw = ps.hardware_interests or []
        if isinstance(hw, list) and hw:
            bits.append(f"hardware=[{'; '.join(str(x).strip() for x in hw[:2] if str(x).strip())}]")
        infra = ps.infrastructure_needs or []
        if isinstance(infra, list) and infra:
            bits.append(f"infra=[{'; '.join(str(x).strip() for x in infra[:2] if str(x).strip())}]")
        proj = ps.current_projects or []
        if isinstance(proj, list) and proj:
            bits.append(f"projects=[{'; '.join(str(x).strip() for x in proj[:3] if str(x).strip())}]")
        if ps.notes:
            bits.append(f"notes={ps.notes[:200].strip()}")
    extra = (" " + " ".join(bits)) if bits else ""
    return f"- {tag}{extra}".strip()


def _run_person_report(report: LeadReport, *, hub_org_id: int) -> None:
    person = db.session.get(Person, report.target_person_id)
    if person is None:
        raise ValueError("Target person missing")

    set_lead_report_phase("Person candidate: loading hub persona + recent target evidence...")
    hp = load_hub_persona()

    owned_items, target_evidence_block, persona_json_str = _person_target_block(person)
    allowed_tgt = {c.id for c in owned_items}

    report.input_fingerprint = _fingerprint_hub_target(
        hub_ids=[],
        target_person_id=person.id,
        target_organization_id=None,
        target_building_id=None,
        target_region_id=None,
    )

    prompt_raw = normalize_prompt_body(
        _load_prompt_file("lead_report_person_synthesis.txt")
        .replace("{{hub_long_agent_prompt}}", hp.get("long_agent_prompt", ""))
        .replace("{{hub_fit_scoring}}", json.dumps(hp.get("lead_fit_scoring", {}), ensure_ascii=False))
        .replace("{{hub_signals}}", json.dumps(hp.get("signals", {}), ensure_ascii=False))
        .replace(
            "{{hub_outreach_email_pattern}}",
            hp.get("outreach_strategy", {}).get("email_pattern", {}).get("body", ""),
        )
        .replace("{{persona_json}}", persona_json_str)
        .replace("{{target_evidence}}", target_evidence_block or "(empty)")
    )

    set_lead_report_phase("Person candidate: single-pass synthesis...")
    data = run_lead_report_llm(prompt_raw, json_format=True)
    if data is None:
        raise RuntimeError("Synthesis LLM returned no usable JSON — try SYNAPSE_LEAD_REPORT_NUM_CTX.")

    exe = data.get("executive_summary") if isinstance(data, dict) else None
    if not isinstance(exe, str) or not exe.strip():
        exe = json.dumps(data, ensure_ascii=False)[:32000]

    routes = _normalize_routes(data, hub_ids=set(), target_ids=allowed_tgt)

    raw_fit = data.get("fit_score")
    fit_score: float | None = None
    if isinstance(raw_fit, (int, float)):
        fit_score = max(0.0, min(1.0, float(raw_fit)))

    email_draft_val = str(data.get("email_draft") or "").strip() or None

    raw_pos = data.get("positive_signals")
    positive_signals_val = [str(s).strip() for s in raw_pos if str(s).strip()] if isinstance(raw_pos, list) else []

    raw_unc = data.get("uncertainties")
    uncertainties_val = [str(s).strip() for s in raw_unc if str(s).strip()] if isinstance(raw_unc, list) else []

    likely_pain = str(data.get("likely_technical_pain") or "").strip() or None

    report.executive_summary = exe.strip() or "(Synthesis omitted.)"
    report.collaboration_routes_json = json.dumps(routes, ensure_ascii=False)
    report.ranked_contacts_json = None
    report.model_used = lead_report_model_label()
    report.fit_score = fit_score
    report.email_draft = email_draft_val
    report.positive_signals = positive_signals_val
    report.uncertainties = uncertainties_val
    report.likely_technical_pain = likely_pain


def _run_org_building_region_report(report: LeadReport, *, hub_org_id: int) -> None:
    org_ids, subject_label = _organization_ids_for_report(report)
    if not subject_label:
        raise ValueError("Lead candidate has no organization, building, or region target.")

    people, roster = _people_roster_for_orgs(org_ids, hub_organization_id=int(hub_org_id))

    set_lead_report_phase("Organization / building / region candidate: loading hub persona + roster...")
    hub_context = hub_persona_context_block()
    allowed_people_ids = {p.id for p in people}

    report.input_fingerprint = _fingerprint_hub_target(
        hub_ids=[],
        target_person_id=None,
        target_organization_id=report.target_organization_id,
        target_building_id=report.target_building_id,
        target_region_id=report.target_region_id,
    )

    tmpl = normalize_prompt_body(_load_prompt_file("lead_report_organization_place.txt"))
    prompt = (
        tmpl.replace("{{subject_label}}", subject_label)
        .replace("{{hub_context}}", hub_context)
        .replace("{{people_roster}}", roster)
    )

    set_lead_report_phase("Organization / building / region candidate: rollup synthesis...")
    data = run_lead_report_llm(prompt, json_format=True)
    if data is None or not isinstance(data, dict):
        raise RuntimeError("Organization rollup LLM returned no usable JSON/object.")

    exe = data.get("executive_summary")
    if not isinstance(exe, str) or not exe.strip():
        exe = ""

    routes = _normalize_routes(data, hub_ids=set(), target_ids=set())
    for r in routes:
        r.pop("target_evidence_refs", None)

    rc_raw = data.get("ranked_contacts")
    ranked: list[dict[str, Any]] = []
    if isinstance(rc_raw, list):
        seen_p: set[int] = set()
        for obj in rc_raw[:12]:
            if not isinstance(obj, dict):
                continue
            try:
                pid = int(obj.get("person_id"))
            except (TypeError, ValueError):
                continue
            if pid not in allowed_people_ids or pid in seen_p:
                continue
            seen_p.add(pid)
            scr = obj.get("score")
            score_f = 0.5
            if isinstance(scr, (int, float)):
                score_f = max(0.0, min(1.0, float(scr)))
            ranked.append(
                {
                    "person_id": pid,
                    "score": score_f,
                    "why": str(obj.get("why") or "").strip()[:8000],
                    "opener": str(obj.get("opener") or "").strip()[:2000] or None,
                }
            )

    report.executive_summary = exe.strip() or "(No summary produced.)"
    report.collaboration_routes_json = json.dumps(routes, ensure_ascii=False)
    report.ranked_contacts_json = json.dumps(ranked, ensure_ascii=False) if ranked else None
    report.model_used = lead_report_model_label()


def effective_hub_organization_id(report: LeadReport) -> int | None:
    if report.hub_organization_id is not None:
        return int(report.hub_organization_id)
    org = Organization.query.filter_by(is_hub=True).first()
    return int(org.id) if org is not None else None


def run_lead_report_job(report_id: int) -> None:
    """Synchronous runner (called from worker thread inside app_context)."""

    report = LeadReport.query.filter_by(id=int(report_id)).first()
    if report is None:
        return

    now = datetime.now(timezone.utc)
    report.status = "running"
    report.started_at = now
    report.error_detail = None
    db.session.commit()

    try:
        set_lead_report_phase("Resolving Hub corpus organization…")
        hub_oid = effective_hub_organization_id(report)
        if hub_oid is None:
            raise ValueError(
                "Set Hub corpus organization on the candidate or under Leads settings before running."
            )

        report.hub_organization_id = int(hub_oid)
        db.session.commit()

        if report.target_person_id is not None:
            _run_person_report(report, hub_org_id=hub_oid)
        elif (
            report.target_organization_id is not None
            or report.target_building_id is not None
            or report.target_region_id is not None
        ):
            _run_org_building_region_report(report, hub_org_id=hub_oid)
        else:
            raise ValueError("Lead candidate has no target subject.")

        report.status = "ok"
        report.completed_at = datetime.now(timezone.utc)
    except Exception as e:  # noqa: BLE001
        report.status = "failed"
        report.error_detail = str(e)[:8000]
        report.completed_at = datetime.now(timezone.utc)
    finally:
        db.session.commit()


def enqueue_lead_report(
    *,
    hub_organization_id: int | None,
    target_person_id: int | None,
    target_organization_id: int | None,
    target_building_id: int | None,
    target_region_id: int | None,
) -> LeadReport:
    """Persist queued report row."""

    one_hot = sum(
        1
        for x in (target_person_id, target_organization_id, target_building_id, target_region_id)
        if x is not None
    )
    if one_hot != 1:
        raise ValueError("Exactly one of person/organization/building/region target ids is required.")

    row = LeadReport(
        hub_organization_id=int(hub_organization_id) if hub_organization_id else None,
        target_person_id=target_person_id,
        target_organization_id=target_organization_id,
        target_building_id=target_building_id,
        target_region_id=target_region_id,
        status="queued",
    )
    db.session.add(row)
    db.session.flush()
    return row
