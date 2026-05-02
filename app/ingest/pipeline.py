"""Poll enabled sources and enqueue lead rows."""

from __future__ import annotations

import hashlib
import ssl
import time
import traceback
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import desc

from app.extensions import db
from app.ingest.ollama_client import OLLAMA_MODEL, try_enrich_lead
from app.ingest.rss import fetch_feed, iter_entries
from app.models import ContentItem, LeadCandidate, PollLog, Source, SourceSnapshot

_SSL = ssl.create_default_context()


def _published_dt(pe) -> datetime | None:
    if not pe.published_parsed:
        return None
    try:
        ts = time.mktime(pe.published_parsed)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _ingest_rss_source(source: Source) -> int:
    new_items = 0
    parsed = fetch_feed(source.url)
    for pe in iter_entries(parsed):
        existing = ContentItem.query.filter_by(source_id=source.id, external_id=pe.external_id).first()
        if existing:
            continue
        ci = ContentItem(
            source_id=source.id,
            external_id=pe.external_id,
            title=pe.title,
            link=pe.link or None,
            published_at=_published_dt(pe),
            snippet=pe.snippet or None,
        )
        db.session.add(ci)
        db.session.flush()
        new_items += 1
        enriched = try_enrich_lead(pe.title, pe.link, pe.snippet or "")
        if enriched and isinstance(enriched, dict):
            headline = (enriched.get("headline") or pe.title).strip() or pe.title
            angle = enriched.get("angle")
            out = enriched.get("outreach_snippet")
            tags = enriched.get("hub_tags")
            model_used = OLLAMA_MODEL
        else:
            headline = (pe.title or "Untitled")[:2000]
            angle = (pe.snippet or None)[:8000] if pe.snippet else None
            out = None
            tags = None
            model_used = None
        lead = LeadCandidate(
            content_item_id=ci.id,
            headline=headline,
            angle=str(angle)[:8000] if angle else None,
            outreach_snippet=str(out)[:8000] if out else None,
            hub_tags=str(tags)[:2000] if tags else None,
            model_used=model_used,
        )
        db.session.add(lead)
    return new_items


def _ingest_html_snapshots(source: Source) -> int:
    req = urllib.request.Request(source.url, headers={"User-Agent": "SynapseIngest/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=_SSL) as resp:
        body = resp.read()
    h = hashlib.sha256(body).hexdigest()
    last = (
        SourceSnapshot.query.filter_by(source_id=source.id)
        .order_by(desc(SourceSnapshot.fetched_at))
        .first()
    )
    if last and last.body_sha256 == h:
        return 0
    snap = SourceSnapshot(source_id=source.id, body_sha256=h)
    db.session.add(snap)
    return 1


def run_poll() -> PollLog:
    """Poll all enabled, non-pending sources. Always writes a PollLog row."""
    lines: list[str] = []
    ok = True
    sources = Source.query.filter_by(enabled=True, pending=False).order_by(Source.id).all()

    try:
        for s in sources:
            try:
                if s.kind == "rss_feed":
                    n = _ingest_rss_source(s)
                    lines.append(f"[rss] {s.label or s.url}: {n} new item(s)")
                elif s.kind == "html_page":
                    n = _ingest_html_snapshots(s)
                    lines.append(f"[html] {s.label or s.url}: snapshot delta +{n}")
                else:
                    lines.append(f"[skip] unknown kind {s.kind!r} id={s.id}")
            except Exception as e:  # noqa: BLE001
                ok = False
                lines.append(f"[error] source id={s.id} {s.url}: {e}")
                lines.append(traceback.format_exc()[-2000:])
        db.session.commit()
    except Exception:
        db.session.rollback()
        ok = False
        lines.append(traceback.format_exc())
        log = PollLog(ok=False, detail="\n".join(lines))
        db.session.add(log)
        db.session.commit()
        return log

    log = PollLog(ok=ok, detail="\n".join(lines) if lines else "(no sources)")
    db.session.add(log)
    db.session.commit()
    return log
