"""Mark person/org public digest stale after new ingest (post-poll; no LLM here)."""

from __future__ import annotations

from app.extensions import db
from app.models import Organization, Person, Source


def collect_stale_targets_for_source(source: Source, *, person_ids: set[int], org_ids: set[int]) -> None:
    """Mutate id sets when ``source`` had new public content worth a digest refresh."""

    if source.person_id:
        pid = int(source.person_id)
        person_ids.add(pid)
        p = db.session.get(Person, pid)
        if p is not None:
            for org in p.organizations:
                org_ids.add(int(org.id))
    elif source.organization_id:
        org_ids.add(int(source.organization_id))


def apply_public_digest_stale_flags(*, person_ids: set[int], org_ids: set[int]) -> None:
    """Set ``public_digest_stale`` on affected rows (idempotent)."""

    for pid in person_ids:
        p = db.session.get(Person, int(pid))
        if p is not None:
            p.public_digest_stale = True
    for oid in org_ids:
        o = db.session.get(Organization, int(oid))
        if o is not None:
            o.public_digest_stale = True
