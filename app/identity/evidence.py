"""Gather ContentItems for person identity prompts (deterministic overlays + LLM input)."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.ingest.html_extract import plaintext_excerpt as _plaintext_excerpt
from app.domain.effective_sources import source_ids_for_organization
from app.domain.entity_associations import organization_ids_for_place
from app.models import ContentItem, Person, Place, Source, SourceSnapshot

_PUBMED_ID = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/\s*(\d+)", re.I)
DEFAULT_IDENTITY_CHUNK_MAX = 4000


def _normalize_utc(dt: datetime | None) -> datetime | None:
    """SQLite/driver may yield naive timestamps; comparisons need aware UTC."""

    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _coerce_dt(item: ContentItem) -> datetime:
    raw = item.published_at or item.first_seen_at
    n = _normalize_utc(raw)
    return n if n is not None else datetime.min.replace(tzinfo=timezone.utc)


def enabled_owned_source_ids(person_id: int) -> list[int]:
    rows = (
        Source.query.filter(
            Source.person_id == int(person_id),
            Source.pending.is_(False),
            Source.enabled.is_(True),
        )
        .with_entities(Source.id)
        .distinct()
        .all()
    )
    return [row[0] for row in rows]


def paper_count_for_owned_sources(person: Person, *, days: int) -> int:
    """Count publications in-window across **all** items on owned sources (not only the persona LLM subset)."""

    sids = enabled_owned_source_ids(person.id)
    if not sids:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    cols = ContentItem.query.filter(ContentItem.source_id.in_(sids)).with_entities(
        ContentItem.published_at,
        ContentItem.first_seen_at,
    )
    n = 0
    for pub, seen in cols:
        dt = _normalize_utc(pub or seen)
        if dt is not None and dt >= cutoff:
            n += 1
    return n


def gather_content_items_for_person(person: Person, *, limit: int = 42) -> list[ContentItem]:
    """Latest items across owned sources (enabled, non-pending)."""

    flat = enabled_owned_source_ids(person.id)
    if not flat:
        return []
    rows = (
        ContentItem.query.filter(ContentItem.source_id.in_(flat))
        .options(joinedload(ContentItem.source))
        .order_by(desc(ContentItem.first_seen_at))
        .limit(max(1, int(limit)))
        .all()
    )
    rows.sort(key=_coerce_dt, reverse=True)
    return rows


def content_fingerprint(items: list[ContentItem]) -> str:
    from hashlib import sha256

    raw = "|".join(str(ci.id) for ci in sorted(items, key=lambda x: x.id))
    return sha256(raw.encode()).hexdigest()[:64]


def identity_paper_overlay_days() -> int:
    """Rolling window for ``paper_count_last_90d`` overlay."""

    try:
        d = int(os.environ.get("SYNAPSE_IDENTITY_PAPER_DAYS", "365"))
    except (TypeError, ValueError):
        d = 365
    return max(7, min(1095, d))


def _maybe_pmid(link: str | None) -> str | None:
    if not link:
        return None
    m = _PUBMED_ID.search(link)
    return m.group(1) if m else None


def raw_papers_snapshot(items: list[ContentItem], *, cap: int = 40) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ci in items[:cap]:
        dt = ci.published_at or ci.first_seen_at
        out.append(
            {
                "title": (ci.title or "").strip(),
                "link": ci.link or "",
                "pmid": _maybe_pmid(ci.link),
                "pubdate": dt.isoformat() if dt else None,
                "content_item_id": ci.id,
            }
        )
    return out


def sources_last_scanned_for_person(person: Person) -> dict[str, str | None]:
    """Latest snapshot time per ingest kind among this person's owned sources."""

    sids = [r[0] for r in Source.query.with_entities(Source.id).filter(Source.person_id == person.id).all()]
    if not sids:
        return {}
    kinds = dict(db.session.query(Source.id, Source.kind).filter(Source.id.in_(sids)).all())
    snaps = SourceSnapshot.query.filter(SourceSnapshot.source_id.in_(sids)).all()
    by_kind_best: dict[str, datetime | None] = {}
    for sn in snaps:
        kind = kinds.get(sn.source_id) or "unknown"
        prev = by_kind_best.get(kind)
        fet = _normalize_utc(sn.fetched_at)
        if fet is None:
            continue
        prev_u = _normalize_utc(prev)
        if prev_u is None or fet >= prev_u:
            by_kind_best[kind] = sn.fetched_at
    return {
        k: v.isoformat() if v else None
        for k, v in sorted(by_kind_best.items(), key=lambda x: x[0])
    }


def chunks_for_prompt(items: list[ContentItem]) -> str:
    """Pack evidence newest-first."""

    budget = max(16000, int(os.environ.get("SYNAPSE_IDENTITY_CONTENT_BUDGET_CHARS", "56000")))
    chunk_max = max(
        600,
        min(12000, int(os.environ.get("SYNAPSE_IDENTITY_CHUNK_MAX_CHARS", str(DEFAULT_IDENTITY_CHUNK_MAX)))),
    )

    try:
        full_text_n = int(os.environ.get("SYNAPSE_IDENTITY_FULL_TEXT_ITEMS", "14"))
    except ValueError:
        full_text_n = 14
    full_text_n = max(4, min(120, full_text_n))

    blocks: list[str] = []
    remaining = budget
    for idx, ci in enumerate(items):
        title_line = (ci.title or "").strip()
        lk = ci.link or ""
        when = ci.published_at or ci.first_seen_at
        when_s = when.isoformat() if when else ""
        skind = ci.source.kind if ci.source else ""
        head = (
            f"SYNAPSE_CONTENT_ITEM_ID={ci.id}\nSOURCE_KIND={skind}\n"
            f"title={title_line}\nlink={lk}\npublished={when_s}\ntext:\n"
        )
        overhead = len(head)
        if remaining <= overhead + 120:
            break

        if idx < full_text_n:
            cap = chunk_max
        else:
            cap = max(380, min(900, chunk_max // 6, remaining - overhead))

        allot = min(cap, max(120, remaining - overhead))
        body = _plaintext_excerpt(ci.snippet or "", allot).strip()
        block = head + body
        blocks.append(block)
        remaining -= len(block)

    return "\n\n---\n\n".join(blocks)


def person_has_identity_evidence_signals(person_id: int) -> bool:
    """True if persona rebuild is likely useful (poll produced at least one content item somewhere)."""

    sids = enabled_owned_source_ids(int(person_id))
    if not sids:
        return False
    return (
        ContentItem.query.filter(ContentItem.source_id.in_(sids)).with_entities(ContentItem.id).first() is not None
    )


def organization_has_identity_evidence_signals(organization_id: int) -> bool:
    """True if rollup has any ingested signals along effective org corpus sources."""

    sids = source_ids_for_organization(int(organization_id))
    if not sids:
        return False
    return (
        ContentItem.query.filter(ContentItem.source_id.in_(list(sids)))
        .with_entities(ContentItem.id)
        .first()
        is not None
    )


def place_has_identity_evidence_signals(place_id: int) -> bool:
    for oid in organization_ids_for_place(int(place_id)):
        if organization_has_identity_evidence_signals(int(oid)):
            return True
    return False
