"""Poll enabled sources; capture ContentItem snapshots (lead reports run separately from Leads)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any
import os
import hashlib
import ssl
import calendar
import traceback
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import desc

from app.extensions import db
from app.ingest.html_extract import (
    extract_snapshot_text_main_preferred,
    html_poll_content_external_id,
    plaintext_excerpt,
)
from app.ingest.ollama_client import html_page_llm_prompt_char_budget, try_summarize_html_page
from app.ingest.rss import fetch_feed, iter_entries
from app.ingest.urlnorm import stable_catalog_url
from app.identity.staleness import mark_identity_stale_from_xor_change
from app.models import ContentItem, PollLog, Source, SourceSnapshot
from app.public_feed.curate import clear_public_feed_curation
from app.public_digest.staleness import apply_public_digest_stale_flags, collect_stale_targets_for_source

_SSL = ssl.create_default_context()


def _fetch_source_url_body(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "SynapseIngest/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=_SSL) as resp:
        return resp.read()


def _compute_html_page_title_snippet(url: str, body: bytes) -> tuple[str, str]:
    """HTML body → ingest title/snippet (extract + optional LLM), matching normal poll behavior."""

    title_guess, plain = extract_snapshot_text_main_preferred(body)
    prompt_budget = html_page_llm_prompt_char_budget()
    excerpt_for_llm = plaintext_excerpt(plain, prompt_budget)

    ci_title = (title_guess or url).strip()[:4096]
    fallback_snip = _html_env_int("SYNAPSE_HTML_PAGE_FALLBACK_SNIPPET_CHARS", 16_000, 2_000)
    ci_snippet = plaintext_excerpt(plain, fallback_snip) if plain else ""
    snippet_store_cap = _html_env_int("SYNAPSE_HTML_PAGE_SNIPPET_STORE_MAX", 28_000, 8_000)

    if excerpt_for_llm and _html_page_llm_enabled():
        summed = try_summarize_html_page(
            url=url,
            page_title_guess=title_guess,
            plaintext_excerpt=excerpt_for_llm,
        )
        if isinstance(summed, dict):
            t = (summed.get("title") or "").strip()
            if t:
                ci_title = t[:4096]
            sn = summed.get("snippet")
            if sn is not None:
                ci_snippet = str(sn).strip()[:snippet_store_cap]

    return (ci_title or "Web page snapshot"), (ci_snippet or "").strip()


def refresh_html_page_content_item(source: Source, *, commit: bool = True) -> dict[str, Any]:
    """Fetch URL and UPSERT ``ContentItem`` title/snippet for semantic ``mainsha:`` dedupe key.

    Skips inserting ``SourceSnapshot`` rows so poll timeline stays unchanged while text is regenerated.

    Returns a status dict suitable for admin UI/logging.
    """

    sid = source.id
    if source.kind != "html_page":
        return {
            "status": "skipped",
            "source_id": sid,
            "detail": f"source kind is {source.kind!r}, not html_page",
            "external_id": None,
            "body_sha256": None,
            "content_item_id": None,
        }

    try:
        body = _fetch_source_url_body(source.url)
    except Exception as e:  # noqa: BLE001
        return {
            "status": "error",
            "source_id": sid,
            "detail": str(e),
            "external_id": None,
            "body_sha256": None,
            "content_item_id": None,
        }

    h = hashlib.sha256(body).hexdigest()
    ext_id = html_poll_content_external_id(body)
    ci_title, ci_snippet = _compute_html_page_title_snippet(source.url, body)

    existing = ContentItem.query.filter_by(source_id=sid, external_id=ext_id).first()
    if existing:
        existing.title = ci_title
        existing.link = source.url
        existing.snippet = ci_snippet or None
        clear_public_feed_curation(existing)
        cid = existing.id
        outcome = "updated"
    else:
        row = ContentItem(
            source_id=sid,
            external_id=ext_id,
            title=ci_title,
            link=source.url,
            snippet=ci_snippet or None,
        )
        db.session.add(row)
        db.session.flush()
        cid = row.id
        outcome = "created"

    if outcome == "created":
        _sp: set[int] = set()
        _so: set[int] = set()
        collect_stale_targets_for_source(source, person_ids=_sp, org_ids=_so)
        apply_public_digest_stale_flags(person_ids=_sp, org_ids=_so)

    mark_identity_stale_from_xor_change(
        before_person_id=source.person_id,
        before_org_id=source.organization_id,
        after_person_id=source.person_id,
        after_org_id=source.organization_id,
    )

    if commit:
        db.session.commit()
    return {
        "status": outcome,
        "source_id": sid,
        "detail": "",
        "external_id": ext_id,
        "body_sha256": h,
        "content_item_id": cid,
    }


def refresh_html_page_content_items(source_ids: Iterable[int], *, commit: bool = True) -> list[dict[str, Any]]:
    """Batch ``refresh_html_page_content_item`` in one transaction."""

    out: list[dict[str, Any]] = []
    for raw in sorted({int(x) for x in source_ids}):
        src = db.session.get(Source, raw)
        if src is None:
            out.append(
                {
                    "status": "skipped",
                    "source_id": raw,
                    "detail": "source not found",
                    "external_id": None,
                    "body_sha256": None,
                    "content_item_id": None,
                }
            )
            continue
        out.append(refresh_html_page_content_item(src, commit=False))
    if commit:
        db.session.commit()
    return out


def _html_env_int(key: str, default: int, floor: int) -> int:
    raw = (os.environ.get(key) or "").strip()
    if not raw:
        return default
    try:
        return max(floor, int(raw))
    except ValueError:
        return default


def _html_page_llm_enabled() -> bool:
    """Use Ollama to condense new html_page snapshots (config + app context aware)."""

    try:
        from flask import current_app

        return bool(current_app.config.get("SYNAPSE_HTML_PAGE_LLM", True))
    except RuntimeError:
        return True


def _published_dt(pe) -> datetime | None:
    """Parse feedparser's ``published_parsed`` (UTC 9-tuple); never use ``time.mktime`` (local-time)."""

    if not pe.published_parsed:
        return None
    try:
        ts = calendar.timegm(pe.published_parsed)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (OverflowError, OSError, ValueError, TypeError):
        return None


def _ingest_rss_source(source: Source) -> int:
    new_items = 0
    parsed = fetch_feed(source.url)
    for pe in iter_entries(parsed):
        existing = ContentItem.query.filter_by(source_id=source.id, external_id=pe.external_id).first()
        if existing:
            continue
        raw_link = (pe.link or "").strip()
        catalog_link = stable_catalog_url(raw_link) if raw_link else None
        ci = ContentItem(
            source_id=source.id,
            external_id=pe.external_id,
            title=pe.title,
            link=catalog_link,
            published_at=_published_dt(pe),
            snippet=pe.snippet or None,
        )
        db.session.add(ci)
        db.session.flush()
        new_items += 1
    return new_items


def _ingest_html_source(source: Source) -> tuple[int, int]:
    """Fetch URL; record raw-byte snapshot; add ``ContentItem`` only when semantic ``mainsha`` changes."""

    body = _fetch_source_url_body(source.url)
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

    ext_id = html_poll_content_external_id(body)
    if ContentItem.query.filter_by(source_id=source.id, external_id=ext_id).first():
        return snapshot_delta, 0

    ci_title, ci_snippet = _compute_html_page_title_snippet(source.url, body)

    ci = ContentItem(
        source_id=source.id,
        external_id=ext_id,
        title=ci_title,
        link=source.url,
        snippet=ci_snippet or None,
    )
    db.session.add(ci)
    return snapshot_delta, 1


PollStepCallback = Callable[..., None]


def run_poll(*, on_source_step: PollStepCallback | None = None) -> PollLog:
    """Poll all enabled, non-pending sources. Always writes a PollLog row.

    Lead reports run separately from the admin Leads page.
    """

    lines: list[str] = []
    ok = True
    sources = Source.query.filter_by(enabled=True, pending=False).order_by(Source.id).all()
    total = len(sources)
    stale_person_ids: set[int] = set()
    stale_org_ids: set[int] = set()

    try:
        for i, s in enumerate(sources):
            if on_source_step is not None:
                on_source_step(phase="running", index=i, total=total, source=s)
            try:
                if s.kind == "rss_feed":
                    n = _ingest_rss_source(s)
                    line = f"[rss] {s.url}: {n} new item(s)"
                    lines.append(line)
                    if n > 0:
                        collect_stale_targets_for_source(s, person_ids=stale_person_ids, org_ids=stale_org_ids)
                elif s.kind == "html_page":
                    snaps, contents = _ingest_html_source(s)
                    line = f"[html] {s.url}: snapshot +{snaps}; content items +{contents}"
                    lines.append(line)
                    if contents > 0:
                        collect_stale_targets_for_source(s, person_ids=stale_person_ids, org_ids=stale_org_ids)
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
        apply_public_digest_stale_flags(person_ids=stale_person_ids, org_ids=stale_org_ids)
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

    if ok and sources:
        try:
            import os

            from app.identity.builder import rebuild_person_identities_bounded

            burst = int(os.environ.get("SYNAPSE_POLL_IDENTITY_BURST", "6"))
            rebuild_person_identities_bounded([s.id for s in sources], max_entities=burst)
        except Exception:
            pass

    return log
