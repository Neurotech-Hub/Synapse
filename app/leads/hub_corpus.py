"""Hub-side source IDs for the Hub corpus organization (reports, personas)."""

from __future__ import annotations

from app.domain.effective_sources import source_ids_for_organization
from app.extensions import db
from app.models import Source


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
