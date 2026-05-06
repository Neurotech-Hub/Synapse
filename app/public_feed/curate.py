"""Manual batch LLM curation for public Latest (writes ContentItem overlay columns)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.ingest.llm_client import public_feed_curate_model_label, run_public_feed_curate_llm
from app.leads.prompt_loader import prompts_dir
from app.models import ContentItem, Source
from app.public_feed.constants import PIPELINE_SEMVER


def public_feed_input_fingerprint(ci: ContentItem) -> str:
    raw = "|".join(
        [
            ci.title or "",
            ci.snippet or "",
            ci.link or "",
            PIPELINE_SEMVER,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:128]


def clear_public_feed_curation(ci: ContentItem | None) -> None:
    if ci is None:
        return
    ci.public_feed_verdict = None
    ci.public_feed_display_title = None
    ci.public_feed_display_blurb = None
    ci.public_feed_input_fingerprint = None
    ci.public_feed_curated_at = None
    ci.public_feed_model_used = None


def select_candidates_for_curation(limit: int = 48) -> list[ContentItem]:
    """Recent public-source items that have never been curated (verdict NULL)."""

    lim = max(1, min(int(limit), 200))
    rows = (
        ContentItem.query.join(Source, ContentItem.source_id == Source.id)
        .options(joinedload(ContentItem.source))
        .filter(
            Source.pending.is_(False),
            Source.enabled.is_(True),
            ContentItem.public_feed_verdict.is_(None),
        )
        .order_by(desc(func.coalesce(ContentItem.published_at, ContentItem.first_seen_at)))
        .limit(lim)
        .all()
    )
    return rows


def count_uncurated_public_feed_candidates() -> int:
    return int(
        db.session.query(func.count(ContentItem.id))
        .join(Source, ContentItem.source_id == Source.id)
        .filter(
            Source.pending.is_(False),
            Source.enabled.is_(True),
            ContentItem.public_feed_verdict.is_(None),
        )
        .scalar()
        or 0
    )


def _load_curate_prompt_template() -> str:
    p = prompts_dir() / "public_latest_curate.txt"
    return p.read_text(encoding="utf-8")


def _candidate_payload(ci: ContentItem) -> dict[str, Any]:
    src = ci.source
    kind = (src.kind if src is not None else "") or ""
    return {
        "content_item_id": int(ci.id),
        "link": (ci.link or "")[:2048],
        "title": (ci.title or "")[:800],
        "snippet": (ci.snippet or "")[:400],
        "source_kind": kind if kind in ("rss_feed", "html_page") else kind or "unknown",
    }


def _normalize_verdict(raw: Any) -> str | None:
    if raw is None:
        return None
    v = str(raw).strip().lower()
    return v if v in ("show", "hide") else None


def run_public_feed_curation_batch(*, limit: int = 48, commit: bool = True) -> dict[str, Any]:
    """One Ollama call for up to ``limit`` uncurated rows; all-or-nothing apply on success."""

    candidates = select_candidates_for_curation(limit=limit)
    if not candidates:
        return {
            "status": "empty",
            "processed": 0,
            "shown": 0,
            "hidden": 0,
            "detail": "No uncurated public Latest candidates.",
        }

    batch_ids = {int(c.id) for c in candidates}
    tmpl = _load_curate_prompt_template()
    payload = [_candidate_payload(c) for c in candidates]
    prompt = tmpl.replace("{{CANDIDATES_JSON}}", json.dumps(payload, ensure_ascii=False))

    parsed = run_public_feed_curate_llm(prompt)
    if parsed is None:
        return {
            "status": "failed",
            "processed": 0,
            "shown": 0,
            "hidden": 0,
            "detail": "Ollama unreachable or timed out.",
        }
    if not isinstance(parsed, dict):
        return {
            "status": "failed",
            "processed": 0,
            "shown": 0,
            "hidden": 0,
            "detail": "Model returned no JSON object.",
        }

    raw_results = parsed.get("results")
    if not isinstance(raw_results, list):
        return {
            "status": "failed",
            "processed": 0,
            "shown": 0,
            "hidden": 0,
            "detail": "Model JSON missing results array.",
        }

    by_id: dict[int, dict[str, Any]] = {}
    for entry in raw_results:
        if not isinstance(entry, dict):
            continue
        try:
            rid = int(entry.get("content_item_id"))
        except (TypeError, ValueError):
            continue
        if rid not in batch_ids:
            continue
        verdict = _normalize_verdict(entry.get("verdict"))
        if verdict is None:
            return {
                "status": "failed",
                "processed": 0,
                "shown": 0,
                "hidden": 0,
                "detail": f"Invalid verdict for content_item_id={rid}.",
            }
        dt = entry.get("display_title")
        db_ = entry.get("display_blurb")
        title_clean = None
        if dt is not None:
            ts = str(dt).strip()
            title_clean = ts if ts else None
        blurb_clean = None
        blurb_explicit = False
        if db_ is not None:
            blurb_explicit = True
            bs = str(db_).strip()
            blurb_clean = bs if bs else None
        by_id[rid] = {
            "verdict": verdict,
            "display_title": title_clean,
            "display_blurb": blurb_clean,
            "display_blurb_explicit": blurb_explicit,
        }

    if not by_id:
        return {
            "status": "failed",
            "processed": 0,
            "shown": 0,
            "hidden": 0,
            "detail": "Model results did not include any known candidate ids.",
        }

    now = datetime.now(timezone.utc)
    shown = 0
    hidden = 0
    for ci in candidates:
        rec = by_id.get(int(ci.id))
        if rec is None:
            continue
        verdict = rec["verdict"]
        ci.public_feed_verdict = verdict
        ci.public_feed_curated_at = now
        ci.public_feed_model_used = public_feed_curate_model_label()
        ci.public_feed_input_fingerprint = public_feed_input_fingerprint(ci)
        if verdict == "hide":
            ci.public_feed_display_title = None
            ci.public_feed_display_blurb = None
            hidden += 1
        else:
            ci.public_feed_display_title = rec["display_title"]
            if rec["display_blurb_explicit"]:
                ci.public_feed_display_blurb = rec["display_blurb"]
            else:
                ci.public_feed_display_blurb = None
            shown += 1

    if commit:
        db.session.commit()

    return {
        "status": "ok",
        "processed": shown + hidden,
        "shown": shown,
        "hidden": hidden,
        "detail": "",
    }
