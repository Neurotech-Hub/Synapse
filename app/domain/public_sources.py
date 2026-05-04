"""Public-site visibility: enabled, non-pending sources and listable people/organizations."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, func
from sqlalchemy.orm import joinedload

from app.domain.effective_sources import source_ids_for_organization
from app.extensions import db
from app.identity.evidence import enabled_owned_source_ids
from app.ingest.urlnorm import UrlValidationError, canonical_url, stable_catalog_url
from app.models import ContentItem, Organization, Person, Source, person_organization


def _public_link_dedupe_fingerprint(url: str) -> str:
    """Stable identity for ``ContentItem.link`` (PubMed PMID, DOI, or tracking-stripped URL)."""

    s = stable_catalog_url((url or "").strip() or None)
    if s:
        return s.lower().rstrip("/")
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        return canonical_url(raw).lower().rstrip("/")
    except UrlValidationError:
        return raw.split("#", 1)[0].strip().lower()


def _normalize_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _sort_dt(item: ContentItem) -> datetime:
    raw = item.published_at or item.first_seen_at
    n = _normalize_utc(raw)
    return n if n is not None else datetime.min.replace(tzinfo=timezone.utc)


def public_enabled_source_ids_for_organization(organization_id: int) -> list[int]:
    """Source IDs for an org (direct + linked members), restricted to enabled and not pending."""

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


def person_is_publicly_listable(person_id: int) -> bool:
    return bool(enabled_owned_source_ids(int(person_id)))


def organization_is_publicly_listable(organization_id: int) -> bool:
    return bool(public_enabled_source_ids_for_organization(int(organization_id)))


def publicly_listed_people() -> list[Person]:
    return (
        Person.query.join(Source, Source.person_id == Person.id)
        .filter(Source.pending.is_(False), Source.enabled.is_(True))
        .order_by(Person.display_name.asc())
        .distinct()
        .all()
    )


def publicly_listed_organizations() -> list[Organization]:
    oids: set[int] = set()
    for (oid,) in (
        db.session.query(Source.organization_id)
        .filter(
            Source.organization_id.isnot(None),
            Source.pending.is_(False),
            Source.enabled.is_(True),
        )
        .distinct()
        .all()
    ):
        oids.add(int(oid))
    for (oid,) in (
        db.session.query(person_organization.c.organization_id)
        .join(Source, Source.person_id == person_organization.c.person_id)
        .filter(Source.pending.is_(False), Source.enabled.is_(True))
        .distinct()
        .all()
    ):
        oids.add(int(oid))
    if not oids:
        return []
    return Organization.query.filter(Organization.id.in_(oids)).order_by(Organization.display_name.asc()).all()


def public_content_items_for_person(person_id: int, *, limit: int = 48) -> list[ContentItem]:
    sids = enabled_owned_source_ids(int(person_id))
    if not sids:
        return []
    lim = max(1, int(limit))
    rows = (
        ContentItem.query.filter(ContentItem.source_id.in_(sids))
        .options(joinedload(ContentItem.source))
        .order_by(desc(ContentItem.first_seen_at))
        .limit(lim)
        .all()
    )
    rows.sort(key=_sort_dt, reverse=True)
    return rows


def public_content_items_for_organization(organization_id: int, *, limit: int = 48) -> list[ContentItem]:
    sids = public_enabled_source_ids_for_organization(int(organization_id))
    if not sids:
        return []
    lim = max(1, int(limit))
    rows = (
        ContentItem.query.filter(ContentItem.source_id.in_(sids))
        .options(joinedload(ContentItem.source))
        .order_by(desc(ContentItem.first_seen_at))
        .limit(lim)
        .all()
    )
    rows.sort(key=_sort_dt, reverse=True)
    return rows


def latest_public_content_items_globally(*, limit: int = 400) -> list[ContentItem]:
    """Recent items across all public sources (for anti-flood post-processing)."""

    lim = max(1, min(int(limit), 2000))
    rows = (
        ContentItem.query.join(Source, ContentItem.source_id == Source.id)
        .options(joinedload(ContentItem.source))
        .filter(Source.pending.is_(False), Source.enabled.is_(True))
        .order_by(desc(func.coalesce(ContentItem.published_at, ContentItem.first_seen_at)))
        .limit(lim)
        .all()
    )
    rows.sort(key=_sort_dt, reverse=True)
    return rows


def _public_item_dedupe_key(ci: ContentItem) -> tuple[int, str]:
    """One logical story per source + link identity (snapshots, PubMed tracking params, etc.)."""

    sid = int(ci.source_id)
    raw = (ci.link or "").strip()
    if not raw and ci.source is not None:
        raw = (ci.source.url or "").strip()
    if not raw:
        return (sid, f"row:{int(ci.id)}")
    fp = _public_link_dedupe_fingerprint(raw)
    return (sid, fp or f"row:{int(ci.id)}")


def dedupe_latest_items_by_source_link(items: list[ContentItem]) -> list[ContentItem]:
    """Preserve newest-first order; drop older rows that repeat the same (source, canonical link)."""

    seen: set[tuple[int, str]] = set()
    out: list[ContentItem] = []
    for ci in items:
        key = _public_item_dedupe_key(ci)
        if key in seen:
            continue
        seen.add(key)
        out.append(ci)
    return out


def apply_per_source_cap(items: list[ContentItem], *, max_per_source: int, take_total: int) -> list[ContentItem]:
    """Greedy take in existing order (newest first), at most ``max_per_source`` rows per ``source_id``."""

    cap = max(1, int(max_per_source))
    total = max(1, int(take_total))
    counts: dict[int, int] = {}
    out: list[ContentItem] = []
    for ci in items:
        sid = int(ci.source_id)
        if counts.get(sid, 0) >= cap:
            continue
        out.append(ci)
        counts[sid] = counts.get(sid, 0) + 1
        if len(out) >= total:
            break
    return out


def batch_consecutive_by_source(items: list[ContentItem], *, min_batch: int = 2) -> list[dict]:
    """Turn consecutive same-source tail into batch cards for template rendering."""

    if not items:
        return []
    out: list[dict] = []
    i = 0
    while i < len(items):
        sid = items[i].source_id
        j = i
        while j < len(items) and items[j].source_id == sid:
            j += 1
        chunk = items[i:j]
        chunk = dedupe_latest_items_by_source_link(chunk)
        if len(chunk) >= min_batch:
            # Key must not be ``items`` — Jinja resolves ``dict.items`` as the method, not a key.
            out.append({"kind": "batch", "source": chunk[0].source, "batch_items": chunk})
            i = j
        else:
            for ci in chunk:
                out.append({"kind": "single", "item": ci})
            i = j
    return out
