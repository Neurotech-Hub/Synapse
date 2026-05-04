"""Resolve which ingest sources anchor org/person rollup (hub corpus, identity evidence)."""

from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import Person, Source, person_organization


def source_ids_for_organization(organization_id: int) -> set[int]:
    """Sources owned directly by ``organization_id`` ∪ sources owned by people linked to that org."""

    oid = int(organization_id)
    owned_by_org = {
        r[0]
        for r in Source.query.with_entities(Source.id).filter(Source.organization_id == oid).all()
    }
    pid_stmt = select(person_organization.c.person_id).where(person_organization.c.organization_id == oid)
    pid_rows = db.session.execute(pid_stmt).fetchall()
    pids = {int(r[0]) for r in pid_rows}

    owned_by_org_people = set()
    if pids:
        owned_by_org_people = {
            r[0]
            for r in Source.query.with_entities(Source.id).filter(Source.person_id.in_(pids)).all()
        }

    return owned_by_org | owned_by_org_people


def identity_eligible_source_ids_for_organization(organization_id: int) -> list[int]:
    """Org rollup / identity: union of org-linked and member-owned sources, restricted like the poller (enabled, not pending)."""

    raw = source_ids_for_organization(int(organization_id))
    if not raw:
        return []
    rows = (
        Source.query.filter(
            Source.id.in_(raw),
            Source.pending.is_(False),
            Source.enabled.is_(True),
        )
        .with_entities(Source.id)
        .order_by(Source.id.asc())
        .all()
    )
    return [int(r[0]) for r in rows]


def source_ids_linked_to_subject_person(person_id: int) -> list[int]:
    """Direct source ownership for persona evidence (sorted by source id)."""

    rows = Source.query.with_entities(Source.id).filter(Source.person_id == int(person_id)).order_by(Source.id).all()
    return [int(r[0]) for r in rows]
