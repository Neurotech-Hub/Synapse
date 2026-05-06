"""Read-only corpus retrieval for personas and MCP tools (Flask app context required)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, or_
from sqlalchemy.orm import joinedload

from app.domain.effective_sources import identity_eligible_source_ids_for_organization
from app.domain.entity_associations import organization_ids_for_building
from app.extensions import db
from app.identity.evidence import enabled_owned_source_ids
from app.models import Building, ContentItem, Organization, Person, PersonaSnapshot, Source


def _persona_brief(row: PersonaSnapshot) -> dict[str, Any]:
    return {
        "research_focus": row.research_focus or [],
        "methods": row.methods or [],
        "keywords": row.keywords or [],
        "current_projects": row.current_projects or [],
        "funding_signals": row.funding_signals or [],
        "collab_openness_score": row.collab_openness_score,
        "hardware_interests": row.hardware_interests or [],
        "infrastructure_needs": row.infrastructure_needs or [],
        "notes": row.notes or "",
    }


def source_ids_for_entity(entity_type: str, entity_id: int) -> list[int]:
    et = (entity_type or "").strip().lower()
    eid = int(entity_id)
    if et == "person":
        return enabled_owned_source_ids(eid)
    if et == "organization":
        return identity_eligible_source_ids_for_organization(eid)
    if et == "building":
        acc: set[int] = set()
        for oid in organization_ids_for_building(eid):
            acc.update(identity_eligible_source_ids_for_organization(int(oid)))
        return sorted(acc)
    raise ValueError("entity_type must be 'person', 'organization', or 'building'")


def get_entity_persona_snapshot(entity_type: str, entity_id: int) -> dict[str, Any]:
    """Return persona fields for the subject, or ``not_found`` / error payload."""

    et = (entity_type or "").strip().lower()
    eid = int(entity_id)
    row: PersonaSnapshot | None = None
    if et == "person":
        p = db.session.get(Person, eid)
        if p is None:
            return {"error": "not_found", "entity_type": et, "entity_id": eid}
        row = p.persona
    elif et == "organization":
        o = db.session.get(Organization, eid)
        if o is None:
            return {"error": "not_found", "entity_type": et, "entity_id": eid}
        row = o.persona
    elif et == "building":
        b = db.session.get(Building, eid)
        if b is None:
            return {"error": "not_found", "entity_type": et, "entity_id": eid}
        row = b.persona
    else:
        return {"error": "invalid_entity_type", "entity_type": entity_type}

    if row is None:
        return {"entity_type": et, "entity_id": eid, "persona": None}
    d = _persona_brief(row)
    d["prompt_version"] = row.prompt_version
    d["model_used"] = row.model_used
    d["build_status"] = row.build_status
    d["generated_at"] = row.generated_at.isoformat() if row.generated_at else None
    return {"entity_type": et, "entity_id": eid, "persona": d}


def get_entity_evidence(
    entity_type: str,
    entity_id: int,
    *,
    time_window_days: int | None = None,
    limit: int = 40,
) -> dict[str, Any]:
    """Recent ContentItem excerpts tied to entity-owned sources."""

    sids = source_ids_for_entity(entity_type, entity_id)
    if not sids:
        return {"entity_type": entity_type, "entity_id": int(entity_id), "items": [], "sources": []}

    q = (
        ContentItem.query.filter(ContentItem.source_id.in_(sids))
        .options(joinedload(ContentItem.source))
        .order_by(desc(ContentItem.first_seen_at))
    )
    lim = max(1, min(int(limit), 200))
    if time_window_days is not None and int(time_window_days) > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(time_window_days))
        q = q.filter(
            or_(
                ContentItem.first_seen_at >= cutoff,
                ContentItem.published_at >= cutoff,
            )
        )
    rows = q.limit(lim).all()

    items_out: list[dict[str, Any]] = []
    for ci in rows:
        sk = ci.source.kind if ci.source else ""
        snip = (ci.snippet or "")[:2000]
        items_out.append(
            {
                "content_item_id": ci.id,
                "source_id": ci.source_id,
                "source_kind": sk,
                "title": (ci.title or "")[:500],
                "link": ci.link or "",
                "published_at": ci.published_at.isoformat() if ci.published_at else None,
                "first_seen_at": ci.first_seen_at.isoformat() if ci.first_seen_at else None,
                "snippet_excerpt": snip,
            }
        )

    src_rows = Source.query.filter(Source.id.in_(sids)).all()
    sources_out = [
        {
            "source_id": s.id,
            "url": s.url,
            "kind": s.kind,
            "enabled": s.enabled,
            "pending": s.pending,
            "label": s.label,
        }
        for s in src_rows
    ]

    return {
        "entity_type": (entity_type or "").strip().lower(),
        "entity_id": int(entity_id),
        "items": items_out,
        "sources": sources_out,
    }


def get_recent_rss_for_entity(entity_type: str, entity_id: int, *, limit: int = 30) -> dict[str, Any]:
    """Like :func:`get_entity_evidence` but only ``rss_feed`` source kinds."""

    base = get_entity_evidence(
        entity_type, entity_id, time_window_days=None, limit=max(200, int(limit) * 4)
    )
    items = [x for x in base.get("items") or [] if x.get("source_kind") == "rss_feed"]
    lim = max(1, min(int(limit), 100))
    base["items"] = items[:lim]
    base["filter"] = "rss_only"
    return base


def search_entity_corpus(
    entity_type: str,
    entity_id: int,
    query: str,
    *,
    limit: int = 25,
) -> dict[str, Any]:
    """Case-insensitive substring match on title + snippet for entity-owned content."""

    needle = (query or "").strip()
    if len(needle) < 2:
        return {"error": "query_too_short", "min_length": 2}

    sids = source_ids_for_entity(entity_type, entity_id)
    if not sids:
        return {"entity_type": entity_type, "entity_id": int(entity_id), "matches": []}

    pat = f"%{needle}%"
    lim = max(1, min(int(limit), 100))
    rows = (
        ContentItem.query.filter(ContentItem.source_id.in_(sids))
        .filter(or_(ContentItem.title.ilike(pat), ContentItem.snippet.ilike(pat)))
        .options(joinedload(ContentItem.source))
        .order_by(desc(ContentItem.first_seen_at))
        .limit(lim)
        .all()
    )

    matches: list[dict[str, Any]] = []
    for ci in rows:
        matches.append(
            {
                "content_item_id": ci.id,
                "source_id": ci.source_id,
                "source_kind": ci.source.kind if ci.source else "",
                "title": (ci.title or "")[:500],
                "link": ci.link or "",
                "published_at": ci.published_at.isoformat() if ci.published_at else None,
            }
        )
    return {"entity_type": (entity_type or "").strip().lower(), "entity_id": int(entity_id), "matches": matches}


def fetch_content_item_for_entity(
    entity_type: str, entity_id: int, content_item_id: int
) -> dict[str, Any]:
    """Return one item’s full text if owned by the entity (for OpenAI ``fetch`` tool)."""

    sids = set(source_ids_for_entity(entity_type, entity_id))
    if not sids:
        return {"error": "no_sources", "entity_type": entity_type, "entity_id": int(entity_id)}
    ci = db.session.get(ContentItem, int(content_item_id))
    if ci is None or ci.source_id not in sids:
        return {"error": "not_found", "id": str(content_item_id)}
    src = ci.source
    meta: dict[str, Any] = {"source_id": ci.source_id}
    if src is not None:
        meta["source_kind"] = src.kind
        meta["source_url"] = src.url
    text_cap = 500_000
    return {
        "id": str(ci.id),
        "title": (ci.title or "")[:4096],
        "text": (ci.snippet or "")[:text_cap],
        "url": (ci.link or "")[:4096],
        "metadata": meta,
    }


def openai_company_knowledge_search_text(query: str, *, entity_type: str, entity_id: int, limit: int = 25) -> str:
    """JSON string ``{\"results\":[{\"id\",\"title\",\"url\"}]}`` per OpenAI ChatGPT Apps MCP guide."""

    out = search_entity_corpus(entity_type, entity_id, query, limit=limit)
    if out.get("error") == "query_too_short":
        return json.dumps({"results": []})
    matches = out.get("matches") or []
    results: list[dict[str, str]] = []
    for m in matches:
        cid = m.get("content_item_id")
        if cid is None:
            continue
        results.append(
            {
                "id": str(cid),
                "title": (m.get("title") or "")[:2000],
                "url": (m.get("link") or "")[:4096],
            }
        )
    return json.dumps({"results": results})


def openai_company_knowledge_fetch_text(document_id: str, *, entity_type: str, entity_id: int) -> str:
    """JSON string for document payload per OpenAI (``id``, ``title``, ``text``, ``url``, ``metadata``)."""

    raw = (document_id or "").strip()
    try:
        cid = int(raw)
    except ValueError:
        return json.dumps(
            {
                "id": raw,
                "title": "",
                "text": "",
                "url": "",
                "metadata": {"error": "invalid_id"},
            }
        )
    doc = fetch_content_item_for_entity(entity_type, entity_id, cid)
    if doc.get("error"):
        return json.dumps(
            {
                "id": str(cid),
                "title": "",
                "text": "",
                "url": "",
                "metadata": doc,
            }
        )
    return json.dumps(doc)


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)
