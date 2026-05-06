"""Recent-content-biased Hub lead candidate queueing."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc

from app.extensions import db
from app.leads.report_pipeline import enqueue_lead_report, run_lead_report_job
from app.models import ContentItem, LeadReport, Source


@dataclass(frozen=True)
class LeadCandidateQueueResult:
    queued_ids: list[int]
    skipped_existing: int
    skipped_unowned: int


def queue_recent_lead_candidates(*, limit: int = 8, run_now: bool = False) -> LeadCandidateQueueResult:
    """Queue one candidate per recent source owner.

    This is the MVP replacement for graph administration: recent content selects
    the target, and the existing synthesis pipeline produces the candidate.
    """

    rows = (
        ContentItem.query.join(Source)
        .filter(Source.pending.is_(False), Source.enabled.is_(True))
        .order_by(desc(ContentItem.published_at), desc(ContentItem.first_seen_at), desc(ContentItem.id))
        .limit(max(limit * 6, limit))
        .all()
    )
    seen_targets: set[tuple[str, int]] = set()
    queued_ids: list[int] = []
    skipped_existing = 0
    skipped_unowned = 0

    for item in rows:
        source = item.source
        target = _source_target_key(source) if source is not None else None
        if target is None:
            skipped_unowned += 1
            continue
        if target in seen_targets:
            continue
        seen_targets.add(target)
        kind, target_id = target
        if _active_candidate_exists(kind, target_id):
            skipped_existing += 1
            continue
        row = _enqueue_for_target(kind, target_id)
        queued_ids.append(int(row.id))
        if len(queued_ids) >= limit:
            break

    db.session.commit()

    if run_now:
        for candidate_id in queued_ids:
            run_lead_report_job(candidate_id)

    return LeadCandidateQueueResult(
        queued_ids=queued_ids,
        skipped_existing=skipped_existing,
        skipped_unowned=skipped_unowned,
    )


def _source_target_key(source: Source) -> tuple[str, int] | None:
    if source.person_id is not None:
        return ("person", int(source.person_id))
    if source.organization_id is not None:
        return ("organization", int(source.organization_id))
    return None


def _active_candidate_exists(kind: str, target_id: int) -> bool:
    q = LeadReport.query.filter(LeadReport.status.in_(["queued", "running", "ok"]), LeadReport.reviewed_at.is_(None))
    if kind == "person":
        q = q.filter(LeadReport.target_person_id == target_id)
    elif kind == "organization":
        q = q.filter(LeadReport.target_organization_id == target_id)
    else:
        return True
    return db.session.query(q.exists()).scalar()


def _enqueue_for_target(kind: str, target_id: int) -> LeadReport:
    if kind == "person":
        return enqueue_lead_report(
            hub_organization_id=None,
            target_person_id=target_id,
            target_organization_id=None,
            target_building_id=None,
            target_region_id=None,
        )
    if kind == "organization":
        return enqueue_lead_report(
            hub_organization_id=None,
            target_person_id=None,
            target_organization_id=target_id,
            target_building_id=None,
            target_region_id=None,
        )
    raise ValueError(f"Unsupported lead candidate target kind: {kind}")
