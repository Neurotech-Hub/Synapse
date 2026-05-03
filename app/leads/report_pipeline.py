"""Multi-step Hub-centric lead report synthesis (person / organization / place)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.identity.evidence import gather_content_items_for_person, chunks_for_prompt
from app.ingest.html_extract import plaintext_excerpt as _plain_excerpt
from app.ingest.ollama_client import OLLAMA_MODEL, run_lead_report_llm
from app.leads.hub_corpus import hub_source_ids
from app.leads.lead_report_budgets import (
    PIPELINE_SEMVER,
    hub_items_max_default,
    hub_snippet_chars_default,
    org_place_persona_summaries_cap,
    person_content_budget_chars,
    person_owned_items_max,
)
from app.leads.prompt_loader import normalize_prompt_body, prompts_dir
from app.leads.report_progress import set_lead_report_phase
from app.domain.entity_associations import organization_ids_for_place
from app.models import ContentItem, LeadPipelineSettings, LeadReport, Person, PersonaSnapshot, person_organization
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
    cap = hub_items_max_default()
    char_cap = hub_snippet_chars_default()
    contrib = hub_source_ids(hub_organization_id=int(hub_organization_id))
    if not contrib:
        return [], ""

    hub_items = (
        ContentItem.query.filter(ContentItem.source_id.in_(contrib))
        .options(joinedload(ContentItem.source))
        .order_by(desc(ContentItem.first_seen_at))
        .limit(cap)
        .all()
    )
    blk = "\n\n---\n\n".join(_report_snippet_block(h, max_chars=char_cap) for h in hub_items)
    return hub_items, blk


def _fingerprint_hub_target(*, hub_ids: list[int], target_person_id: int | None, target_organization_id: int | None, target_place_id: int | None) -> str:
    h_part = "|".join(str(i) for i in sorted(set(hub_ids)))
    subj = ""
    if target_person_id is not None:
        subj = f"person:{target_person_id}"
    elif target_organization_id is not None:
        subj = f"organization:{target_organization_id}"
    elif target_place_id is not None:
        subj = f"place:{target_place_id}"
    raw = f"{PIPELINE_SEMVER}|hub:[{h_part}]|tgt:{subj}"
    return sha256(raw.encode()).hexdigest()[:64]


def _person_target_block(person: Person) -> tuple[list[ContentItem], str, str]:
    """Owned evidence list, chunked prompt block, persona synopsis."""

    items = gather_content_items_for_person(person, limit=int(person_owned_items_max()))
    chunk = chunks_for_prompt(items)
    bud = max(4000, int(person_content_budget_chars()))
    if len(chunk) > bud:
        chunk = _plain_excerpt(chunk, bud)

    synopsis = "(no persona snapshot available.)"
    ps = PersonaSnapshot.query.filter_by(person_id=person.id).first()
    if ps and ps.build_status == "ok":
        bullets: list[str] = []
        for label, fld in (
            ("focus", ps.research_focus),
            ("methods", ps.methods),
            ("keywords", ps.keywords[:12] if ps.keywords else []),
        ):
            if isinstance(fld, list) and fld:
                bits = "; ".join(str(x).strip() for x in fld[:8] if str(x).strip())
                if bits:
                    bullets.append(f"{label}: {bits}")
        if ps.collab_openness_score is not None:
            bullets.append(f"collab_openness_score: {float(ps.collab_openness_score):.2f}")
        if bullets:
            synopsis = "\n".join(bullets)

    return items, chunk, synopsis


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


def _people_roster(*, org_id: int | None, place_id: int | None) -> tuple[list[Person], str]:
    if org_id is None and place_id is None:
        return [], ""

    q = Person.query.join(person_organization)
    if org_id is not None:
        q = q.filter(person_organization.c.organization_id == int(org_id))
    elif place_id is not None:
        oids = sorted(organization_ids_for_place(int(place_id)))
        if not oids:
            return [], "(No organizations linked to this place.)"
        q = q.filter(person_organization.c.organization_id.in_(oids))

    people = q.distinct().order_by(Person.display_name.asc()).limit(org_place_persona_summaries_cap()).all()

    lines = [_person_compact_line(p.id) for p in people]
    return people, "\n".join(lines) if lines else "(no affiliated people captured.)"


def _person_compact_line(person_id: int) -> str:
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
            kw = " ".join(str(x).strip() for x in ps.keywords[:10] if str(x).strip())
            if kw:
                bits.append(f"keywords={kw}")
    extra = (" " + " ".join(bits)) if bits else ""
    return f"- {tag}{extra}".strip()


def _run_person_report(report: LeadReport, *, hub_org_id: int) -> None:
    person = db.session.get(Person, report.target_person_id)
    if person is None:
        raise ValueError("Target person missing")

    set_lead_report_phase("Person report: gathering Hub + owned context…")
    hub_items, hub_block = _hub_content_block_hub_only(hub_org_id)
    if not hub_items:
        raise ValueError("Hub corpus produced no ingest items — check Hub organization corpus sources.")

    owned_items, target_block, persona_blob = _person_target_block(person)
    allowed_hub = {h.id for h in hub_items}
    allowed_tgt = {c.id for c in owned_items}

    report.input_fingerprint = _fingerprint_hub_target(
        hub_ids=sorted(allowed_hub),
        target_person_id=person.id,
        target_organization_id=None,
        target_place_id=None,
    )

    p1_raw = normalize_prompt_body(
        _load_prompt_file("lead_report_person_synthesis.txt")
        .replace("{{hub_context}}", hub_block or "(empty)")
        .replace("{{target_context}}", target_block or "(empty)")
        .replace("{{persona_context}}", persona_blob)
    )

    set_lead_report_phase("Person report: synthesis (LLM, step 1 of 2)…")
    synth = run_lead_report_llm(p1_raw, json_format=True)
    if synth is None:
        raise RuntimeError("Synthesis LLM returned no usable JSON/object — try SYNAPSE_LEAD_REPORT_NUM_CTX.")

    exe = synth.get("executive_summary") if isinstance(synth, dict) else None
    if not isinstance(exe, str) or not exe.strip():
        # Some models embed prose oddly; salvage JSON string
        exe = json.dumps(synth, ensure_ascii=False)[:32000]

    summary_text = exe.strip() or "(Synthesis omitted — model returned unusable prose.)"

    p2_raw = normalize_prompt_body(
        _load_prompt_file("lead_report_person_routes.txt")
        .replace("{{executive_summary}}", summary_text)
        .replace("{{hub_context}}", hub_block or "(empty)")
        .replace("{{target_context}}", target_block or "(empty)")
    )

    set_lead_report_phase("Person report: collaboration routes (LLM, step 2 of 2)…")
    parsed2 = run_lead_report_llm(p2_raw, json_format=True)
    routes: list[dict[str, Any]] = []
    if isinstance(parsed2, dict):
        routes = _normalize_routes(parsed2, hub_ids=allowed_hub, target_ids=allowed_tgt)

    report.executive_summary = summary_text
    report.collaboration_routes_json = json.dumps(routes, ensure_ascii=False)
    report.ranked_contacts_json = None
    report.model_used = OLLAMA_MODEL


def _hub_content_block_hub_only(hub_org_id: int) -> tuple[list[ContentItem], str]:
    return _hub_items_and_block(hub_organization_id=int(hub_org_id))


def _run_org_place_report(report: LeadReport, *, hub_org_id: int) -> None:
    if report.target_organization_id is not None:
        subject_label = f'organization id={report.target_organization_id}'
        people, roster = _people_roster(org_id=int(report.target_organization_id), place_id=None)
    elif report.target_place_id is not None:
        subject_label = f'place id={report.target_place_id}'
        people, roster = _people_roster(place_id=int(report.target_place_id), org_id=None)
    else:
        raise ValueError("Org/Place report expects target_organization_id or target_place_id.")

    set_lead_report_phase("Organization / place report: gathering Hub + roster…")
    hub_items, hub_block = _hub_items_and_block(hub_organization_id=int(hub_org_id))
    if not hub_items:
        raise ValueError("Hub corpus produced no ingest items — check Hub organization corpus sources.")

    allowed_hub = {h.id for h in hub_items}
    allowed_people_ids = {p.id for p in people}

    report.input_fingerprint = _fingerprint_hub_target(
        hub_ids=sorted(allowed_hub),
        target_person_id=None,
        target_organization_id=report.target_organization_id,
        target_place_id=report.target_place_id,
    )

    tmpl = normalize_prompt_body(_load_prompt_file("lead_report_organization_place.txt"))
    prompt = (
        tmpl.replace("{{subject_label}}", subject_label)
        .replace("{{hub_context}}", hub_block or "(empty)")
        .replace("{{people_roster}}", roster)
    )

    set_lead_report_phase("Organization / place report: rollup (LLM)…")
    data = run_lead_report_llm(prompt, json_format=True)
    if data is None or not isinstance(data, dict):
        raise RuntimeError("Organization rollup LLM returned no usable JSON/object.")

    exe = data.get("executive_summary")
    if not isinstance(exe, str) or not exe.strip():
        exe = ""

    tgt_empty: set[int] = set()

    routes = _normalize_routes(data, hub_ids=allowed_hub, target_ids=tgt_empty)
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
    report.model_used = OLLAMA_MODEL


def effective_hub_organization_id(report: LeadReport) -> int | None:
    if report.hub_organization_id is not None:
        return int(report.hub_organization_id)
    row = db.session.get(LeadPipelineSettings, 1)
    hid = getattr(row, "hub_organization_id", None) if row else None
    return int(hid) if hid is not None else None


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
                "Set Hub corpus organization on the report or under Leads → Hub settings before running."
            )

        if report.target_person_id is not None:
            _run_person_report(report, hub_org_id=hub_oid)
        elif report.target_organization_id is not None or report.target_place_id is not None:
            _run_org_place_report(report, hub_org_id=hub_oid)
        else:
            raise ValueError("Report has no target subject.")

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
    target_place_id: int | None,
) -> LeadReport:
    """Persist queued report row."""

    one_hot = sum(1 for x in (target_person_id, target_organization_id, target_place_id) if x is not None)
    if one_hot != 1:
        raise ValueError("Exactly one of person/organization/place target ids is required.")

    row = LeadReport(
        hub_organization_id=int(hub_organization_id) if hub_organization_id else None,
        target_person_id=target_person_id,
        target_organization_id=target_organization_id,
        target_place_id=target_place_id,
        status="queued",
    )
    db.session.add(row)
    db.session.flush()
    return row
