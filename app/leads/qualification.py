"""Hub-vs-world qualification pass (batch, bounded LLM calls)."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.ingest.ollama_client import OLLAMA_MODEL, run_qualification_llm
from app.leads.entity_resolution import (
    entities_for_union,
    entity_id_for_slug,
    format_entity_catalog_lines,
    normalize_fingerprint,
)
from app.leads.pipeline_settings import get_qualification_runtime_config
from app.leads.prompt_loader import build_qualified_lead_prompt
from app.models import ContentItem, LeadCandidate, LeadGenWatermark, Source


def _snippet_block(ci: ContentItem) -> str:
    body = (ci.snippet or "")[:6000]
    lk = ci.link or ""
    return (
        f"CONTENT_ITEM_ID={ci.id}\n"
        f"title={(ci.title or '').strip()}\n"
        f"link={lk}\n"
        f"snippet={body}"
    )


def _hub_hash(hub_rows: list[ContentItem]) -> str:
    raw = "|".join(str(r.id) for r in hub_rows)
    return sha256(raw.encode()).hexdigest()[:64]


def _parse_hub_ids(data: dict[str, Any]) -> tuple[list[int], int | None]:
    raw = data.get("hub_content_item_ids")
    if not isinstance(raw, list):
        return [], None
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    primary = out[0] if out else None
    return out, primary


def run_lead_qualification() -> dict[str, int]:
    """Process world ContentItems (id watermark) vs recent Hub slice. Caller must ``app_context``."""

    cfg = get_qualification_runtime_config()
    max_hub = int(cfg["max_hub_items"])
    max_candidates = int(cfg["max_candidates_per_run"])
    cat_cap = int(cfg["entity_catalog_max"])
    prompt_ver = str(cfg["prompt_version"]).strip() or "1"

    stats = {"candidates_seen": 0, "qualified": 0, "skipped": 0, "duplicate": 0, "failed": 0}

    watermark = LeadGenWatermark.query.filter_by(scope="global").first()
    if watermark is None:
        watermark = LeadGenWatermark(scope="global", last_candidate_content_item_id=None)
        db.session.add(watermark)
        db.session.commit()

    last_id = watermark.last_candidate_content_item_id or 0

    hub_items = (
        ContentItem.query.join(Source)
        .filter(Source.lead_source.is_(True))
        .order_by(desc(ContentItem.first_seen_at))
        .limit(max_hub)
        .options(
            joinedload(ContentItem.source).selectinload(Source.entities),
        )
        .all()
    )

    if not hub_items:
        stats["skipped"] += 1
        return stats

    hub_block = "\n\n---\n\n".join(_snippet_block(h) for h in hub_items)
    hhash = _hub_hash(hub_items)

    cq = (
        ContentItem.query.join(Source)
        .filter(Source.lead_source.is_(False), ContentItem.id > last_id)
        .order_by(ContentItem.id.asc())
        .limit(max_candidates)
        .options(
            joinedload(ContentItem.source).selectinload(Source.entities),
        )
    )

    newest_seen = last_id

    for cand in cq:
        stats["candidates_seen"] += 1
        newest_seen = max(newest_seen, cand.id)

        ents = entities_for_union(
            hub_items=hub_items,
            candidate_source=cand.source,
            cap=cat_cap,
        )
        catalog = format_entity_catalog_lines(ents)

        cand_block = _snippet_block(cand)
        prompt = build_qualified_lead_prompt(
            hub_context=hub_block,
            candidate=cand_block,
            entity_catalog=catalog,
        )
        parsed = run_qualification_llm(prompt)
        if not isinstance(parsed, dict):
            stats["failed"] += 1
            continue

        if not bool(parsed.get("qualified")):
            stats["skipped"] += 1
            continue

        cid_list, anchor_id = _parse_hub_ids(parsed)
        hub_cited_json = json.dumps(cid_list) if cid_list else None

        slug = parsed.get("primary_entity_slug")
        eid = entity_id_for_slug(str(slug) if slug is not None else None)
        fingerprint = normalize_fingerprint(parsed.get("subject_fingerprint"))

        lead_row = LeadCandidate(
            candidate_content_item_id=cand.id,
            anchor_hub_content_item_id=anchor_id,
            hub_cited_content_item_ids=hub_cited_json,
            hub_context_hash=hhash,
            prompt_version=prompt_ver,
            entity_id=eid,
            subject_fingerprint=fingerprint,
            headline=(parsed.get("headline") or "Lead").strip()[:2000],
            angle=str(parsed.get("angle") or "").strip()[:8000] or None,
            outreach_snippet=str(parsed.get("outreach_snippet") or "").strip()[:8000] or None,
            hub_tags=str(parsed.get("hub_tags") or "").strip()[:2000] or None,
            model_used=OLLAMA_MODEL,
        )

        db.session.add(lead_row)
        try:
            db.session.commit()
            stats["qualified"] += 1
        except IntegrityError:
            db.session.rollback()
            stats["duplicate"] += 1

    w = LeadGenWatermark.query.filter_by(scope="global").first()
    if w is None:
        w = LeadGenWatermark(scope="global", last_candidate_content_item_id=newest_seen)
        db.session.add(w)
    else:
        prev = w.last_candidate_content_item_id or 0
        w.last_candidate_content_item_id = max(prev, newest_seen)
    db.session.commit()
    return stats
