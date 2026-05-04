"""Link helpers (person↔organization, organization→building, building↔organizations)."""

from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import Building, Organization, Person, person_organization


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


def building_id_for_organization(organization_id: int) -> int | None:
    oid = int(organization_id)
    row = db.session.execute(select(Organization.building_id).where(Organization.id == oid)).first()
    if row is None or row[0] is None:
        return None
    return int(row[0])


def organization_ids_for_building(building_id: int) -> set[int]:
    stmt = select(Organization.id).where(Organization.building_id == int(building_id))
    return {int(r[0]) for r in db.session.execute(stmt).fetchall()}


def set_organization_building(*, organization: Organization, building_id: int | None) -> None:
    """Assign at most one building to an organization."""

    if building_id is None:
        organization.building_id = None
        return
    if db.session.get(Building, int(building_id)) is None:
        return
    organization.building_id = int(building_id)


def sync_building_organizations(*, building: Building, organization_ids_ordered: list[int]) -> None:
    """Set each listed organization's building_id to this building; clear building_id for orgs that left."""

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

    bid = int(building.id)
    prev = {o.id for o in Organization.query.filter_by(building_id=bid).all()}

    for oid in prev:
        if oid not in ids:
            org = db.session.get(Organization, oid)
            if org is not None and org.building_id == bid:
                org.building_id = None

    if not ids:
        return

    for oid in ids:
        org = db.session.get(Organization, oid)
        if org is not None:
            org.building_id = bid
