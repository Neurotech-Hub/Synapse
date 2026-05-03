"""Mark persona rollup rows stale when admin/catalog inputs change (no synchronous LLM refresh)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.domain.entity_associations import organization_ids_for_person
from app.identity.evidence import (
    organization_has_identity_evidence_signals,
    person_has_identity_evidence_signals,
    place_has_identity_evidence_signals,
)
from app.models import PersonaSnapshot, Source, organization_place as organization_place_tbl


def _stamp_stale(snapshot: PersonaSnapshot | None) -> None:
    if snapshot is None:
        return
    snapshot.build_status = "stale"
    snapshot.updated_at = datetime.now(timezone.utc)


def mark_person_identity_stale(person_id: int | None) -> None:
    if not person_id:
        return
    _stamp_stale(PersonaSnapshot.query.filter_by(person_id=int(person_id)).first())


def mark_organization_identity_stale(organization_id: int | None) -> None:
    if not organization_id:
        return
    _stamp_stale(PersonaSnapshot.query.filter_by(organization_id=int(organization_id)).first())


def mark_place_identity_stale(place_id: int | None) -> None:
    if not place_id:
        return
    _stamp_stale(PersonaSnapshot.query.filter_by(place_id=int(place_id)).first())


def mark_places_stale_for_organization(organization_id: int | None) -> None:
    if not organization_id:
        return
    oid = int(organization_id)
    rows = (
        db.session.query(organization_place_tbl.c.place_id)
        .filter(organization_place_tbl.c.organization_id == oid)
        .all()
    )
    for row in rows:
        mark_place_identity_stale(int(row[0]))


def mark_stale_for_person_organization_context(person_id: int) -> None:
    """After person-save or XOR link: person snapshot + each affiliated org rollup + linked places."""

    mark_person_identity_stale(person_id)
    for oid in sorted(organization_ids_for_person(int(person_id))):
        mark_organization_identity_stale(int(oid))
        mark_places_stale_for_organization(int(oid))


def mark_identity_stale_for_org_bundle(organization_id: int | None) -> None:
    if not organization_id:
        return
    oid = int(organization_id)
    mark_organization_identity_stale(oid)
    mark_places_stale_for_organization(oid)


def mark_identity_stale_from_person_org_transition(person_id: int, prev_organization_ids: set[int]) -> None:
    """Stale person + rollup/places bundles for every org touched by affiliation edits."""

    cur_ids = organization_ids_for_person(int(person_id))
    ids = set(prev_organization_ids) | cur_ids
    mark_person_identity_stale(person_id)
    for oid in ids:
        mark_identity_stale_for_org_bundle(int(oid))


def mark_identity_stale_from_xor_change(
    *,
    before_person_id: int | None,
    before_org_id: int | None,
    after_person_id: int | None,
    after_org_id: int | None,
) -> None:
    touched_people = {pid for pid in (before_person_id, after_person_id) if pid is not None}
    touched_orgs = {oid for oid in (before_org_id, after_org_id) if oid is not None}
    for pid in touched_people:
        mark_stale_for_person_organization_context(int(pid))
    for oid in touched_orgs:
        mark_identity_stale_for_org_bundle(int(oid))


def mark_identity_stale_after_source_deleted(src: Source) -> None:
    mark_identity_stale_from_xor_change(
        before_person_id=src.person_id,
        before_org_id=src.organization_id,
        after_person_id=None,
        after_org_id=None,
    )


def identity_snapshot_poll_ready(snapshot: PersonaSnapshot) -> bool:
    """Enough ingest data that an LLM persona run is likely worthwhile."""

    if snapshot.person_id:
        return person_has_identity_evidence_signals(snapshot.person_id)
    if snapshot.organization_id:
        return organization_has_identity_evidence_signals(snapshot.organization_id)
    if snapshot.place_id:
        return place_has_identity_evidence_signals(snapshot.place_id)
    return False


def list_stale_persona_snapshots(limit: int = 200):
    """Orm rows for dashboard roster (joined subjects)."""

    q = PersonaSnapshot.query.filter(PersonaSnapshot.build_status == "stale")
    q = q.options(
        joinedload(PersonaSnapshot.person),
        joinedload(PersonaSnapshot.organization),
        joinedload(PersonaSnapshot.place),
    )
    q = q.order_by(PersonaSnapshot.updated_at.desc())
    return q.limit(int(limit)).all()
