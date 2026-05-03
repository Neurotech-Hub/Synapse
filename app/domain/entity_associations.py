"""Many-to-many link helpers (person↔organization, organization↔place)."""

from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import Organization, Person, Place, organization_place as organization_place_tbl, person_organization


def organization_ids_for_person(person_id: int) -> set[int]:
    stmt = select(person_organization.c.organization_id).where(person_organization.c.person_id == int(person_id))
    return {int(r[0]) for r in db.session.execute(stmt).fetchall()}


def sync_person_organizations(*, person: Person, organization_ids_ordered: list[int]) -> None:
    """Replace affiliations; keeps order of first occurrence."""

    seen: set[int] = set()
    ids: list[int] = []
    for raw in organization_ids_ordered:
        oid = int(raw)
        if oid in seen:
            continue
        if db.session.get(Organization, oid) is None:
            continue
        seen.add(oid)
        ids.append(oid)

    if not ids:
        person.organizations = []
        return

    org_objs = Organization.query.filter(Organization.id.in_(ids)).all()
    by_id = {o.id: o for o in org_objs}
    person.organizations = [by_id[i] for i in ids if i in by_id]


def place_ids_for_organization(organization_id: int) -> set[int]:
    stmt = select(organization_place_tbl.c.place_id).where(
        organization_place_tbl.c.organization_id == int(organization_id)
    )
    return {int(r[0]) for r in db.session.execute(stmt).fetchall()}


def organization_ids_for_place(place_id: int) -> set[int]:
    stmt = select(organization_place_tbl.c.organization_id).where(organization_place_tbl.c.place_id == int(place_id))
    return {int(r[0]) for r in db.session.execute(stmt).fetchall()}


def sync_organization_places(*, organization: Organization, place_ids_ordered: list[int]) -> None:
    seen: set[int] = set()
    ids: list[int] = []
    for raw in place_ids_ordered:
        plid = int(raw)
        if plid in seen:
            continue
        if db.session.get(Place, plid) is None:
            continue
        seen.add(plid)
        ids.append(plid)

    if not ids:
        organization.places = []
        return

    places = Place.query.filter(Place.id.in_(ids)).all()
    by_id = {p.id: p for p in places}
    organization.places = [by_id[i] for i in ids if i in by_id]


def sync_place_organizations(*, place: Place, organization_ids_ordered: list[int]) -> None:
    seen: set[int] = set()
    ids: list[int] = []
    for raw in organization_ids_ordered:
        oid = int(raw)
        if oid in seen:
            continue
        if db.session.get(Organization, oid) is None:
            continue
        seen.add(oid)
        ids.append(oid)

    if not ids:
        place.organizations = []
        return

    org_objs = Organization.query.filter(Organization.id.in_(ids)).all()
    by_id = {o.id: o for o in org_objs}
    place.organizations = [by_id[i] for i in ids if i in by_id]
