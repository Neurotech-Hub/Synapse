"""Poll enabled sources; capture ContentItem snapshots (no synchronous lead qualification)."""

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
from app.ingest.ollama_client import try_summarize_html_page
from app.ingest.rss import fetch_feed, iter_entries
from app.models import ContentItem, PollLog, Source, SourceSnapshot

_SSL = ssl.create_default_context()


def _html_page_llm_enabled() -> bool:
    """Use Ollama to condense new html_page snapshots (config + app context aware)."""

    try:
        from flask import current_app

        return bool(current_app.config.get("SYNAPSE_HTML_PAGE_LLM", True))
    except RuntimeError:
        return True


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
    return new_items


def _ingest_html_source(source: Source) -> tuple[int, int]:
    """Fetch URL, dedupe snapshots, add ``ContentItem`` rows on hash change."""

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
    return snapshot_delta, 1


PollStepCallback = Callable[..., None]


def run_poll(*, on_source_step: PollStepCallback | None = None) -> PollLog:
    """Poll all enabled, non-pending sources. Always writes a PollLog row.

    Lead qualification runs separately (see ``SYNAPSE_LEADS_QUALIFY`` admin action).
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
                    lines.append(line)
                elif s.kind == "html_page":
                    snaps, contents = _ingest_html_source(s)
                    line = f"[html] {s.label or s.url}: snapshot +{snaps}; content items +{contents}"
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
