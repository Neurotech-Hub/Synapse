"""Poll enabled sources and enqueue lead rows."""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import ssl
import time
import traceback
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import desc

from app.extensions import db
from app.ingest.html_extract import extract_snapshot_text, plaintext_excerpt
from app.ingest.ollama_client import OLLAMA_MODEL, try_enrich_lead, try_summarize_html_page
from app.ingest.rss import fetch_feed, iter_entries
from app.models import ContentItem, LeadCandidate, PollLog, Source, SourceSnapshot

_SSL = ssl.create_default_context()


def _html_page_llm_enabled() -> bool:
    """Use Ollama to condense new html_page snapshots (config + app context aware)."""

    try:
        from flask import current_app

        return bool(current_app.config.get("SYNAPSE_HTML_PAGE_LLM", True))
    except RuntimeError:
        return True


def _leads_pipeline_enabled(source: Source) -> bool:
    """RSS-linked LeadCandidate rows + Ollama enrichment only when both are true."""

    if not getattr(source, "lead_source", False):
        return False
    try:
        from flask import current_app

        return bool(current_app.config.get("SYNAPSE_LEADS_INGEST", False))
    except RuntimeError:
        return False


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
        if not _leads_pipeline_enabled(source):
            continue
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


def _ingest_html_source(source: Source) -> tuple[int, int]:
    """Fetch URL, dedupe snapshots, add ``ContentItem`` + optional ``LeadCandidate``.

    Returns ``(snapshot_deltas, new_content_items)`` — snapshot delta is ``0`` or ``1``.
    """
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
        return 0, 0

    snap = SourceSnapshot(source_id=source.id, body_sha256=h)
    db.session.add(snap)
    snapshot_delta = 1

    ext_id = f"sha256:{h}"
    if ContentItem.query.filter_by(source_id=source.id, external_id=ext_id).first():
        return snapshot_delta, 0

    title_guess, plain = extract_snapshot_text(body)
    excerpt_for_llm = plaintext_excerpt(plain, 50000)

    ci_title = (title_guess or source.label or source.url).strip()[:4096]
    ci_snippet = plaintext_excerpt(plain, 4000) if plain else ""

    if excerpt_for_llm and _html_page_llm_enabled():
        summed = try_summarize_html_page(
            url=source.url,
            page_title_guess=title_guess,
            plaintext_excerpt=excerpt_for_llm,
        )
        if isinstance(summed, dict):
            t = (summed.get("title") or "").strip()
            if t:
                ci_title = t[:4096]
            sn = summed.get("snippet")
            if sn is not None:
                ci_snippet = str(sn).strip()[:16000]

    ci = ContentItem(
        source_id=source.id,
        external_id=ext_id,
        title=ci_title or "Web page snapshot",
        link=source.url,
        snippet=ci_snippet or None,
    )
    db.session.add(ci)
    db.session.flush()

    content_new = 1
    if not _leads_pipeline_enabled(source):
        return snapshot_delta, content_new

    enriched = try_enrich_lead(ci_title, source.url or "", ci_snippet or "")
    if enriched and isinstance(enriched, dict):
        headline = (enriched.get("headline") or ci_title).strip() or ci_title
        angle = enriched.get("angle")
        out = enriched.get("outreach_snippet")
        tags = enriched.get("hub_tags")
        model_used = OLLAMA_MODEL
    else:
        headline = (ci_title or "Untitled")[:2000]
        angle = (ci_snippet or None)[:8000] if ci_snippet else None
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
    return snapshot_delta, content_new



PollStepCallback = Callable[..., None]


def run_poll(*, on_source_step: PollStepCallback | None = None) -> PollLog:
    """Poll all enabled, non-pending sources. Always writes a PollLog row.

    If ``on_source_step`` is set, it is invoked as:

    - ``on_source_step(phase="running", index=i, total=total, source=s)``
    - ``on_source_step(phase="done", index=i, total=total, source=s, ok=bool, message=str)``
      after each source (``message`` is the summary line for that source).
    """
    lines: list[str] = []
    ok = True
    sources = Source.query.filter_by(enabled=True, pending=False).order_by(Source.id).all()
    total = len(sources)

    try:
        for i, s in enumerate(sources):
            if on_source_step is not None:
                on_source_step(phase="running", index=i, total=total, source=s)
            try:
                if s.kind == "rss_feed":
                    n = _ingest_rss_source(s)
                    line = f"[rss] {s.label or s.url}: {n} new item(s)"
                    if n > 0:
                        try:
                            from flask import current_app

                            ingest = bool(
                                current_app.config.get("SYNAPSE_LEADS_INGEST", False)
                            )
                            if not ingest:
                                line += " — automated lead generation disabled"
                            elif not getattr(s, "lead_source", False):
                                line += " — content only (not a Lead source)"
                        except RuntimeError:
                            pass
                    lines.append(line)
                elif s.kind == "html_page":
                    snaps, contents = _ingest_html_source(s)
                    line = f"[html] {s.label or s.url}: snapshot +{snaps}; content items +{contents}"
                    if contents > 0:
                        try:
                            from flask import current_app

                            ingest_on = bool(
                                current_app.config.get("SYNAPSE_LEADS_INGEST", False)
                            )
                            if not ingest_on:
                                line += " — automated lead generation disabled"
                            elif not getattr(s, "lead_source", False):
                                line += " — content only (not a Lead source)"
                        except RuntimeError:
                            pass
                    lines.append(line)
                else:
                    line = f"[skip] unknown kind {s.kind!r} id={s.id}"
                    lines.append(line)
                if on_source_step is not None:
                    on_source_step(phase="done", index=i, total=total, source=s, ok=True, message=line)
            except Exception as e:  # noqa: BLE001
                ok = False
                lines.append(f"[error] source id={s.id} {s.url}: {e}")
                lines.append(traceback.format_exc()[-2000:])
                err_line = f"[error] source id={s.id} {s.url}: {e}"
                if on_source_step is not None:
                    on_source_step(
                        phase="done", index=i, total=total, source=s, ok=False, message=err_line
                    )
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
