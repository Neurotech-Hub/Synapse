"""Build ``PublicActivityDigest`` rows from recent public ingest (manual admin trigger)."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Any

from sqlalchemy import desc

from app.domain.public_sources import public_content_items_for_organization, public_content_items_for_person
from app.extensions import db
from app.ingest.html_extract import plaintext_excerpt
from app.ingest.ollama_client import OLLAMA_MODEL, run_public_digest_llm
from app.leads.prompt_loader import prompts_dir
from app.models import Organization, Person, PublicActivityDigest
from app.public_digest.constants import PIPELINE_SEMVER, PROMPT_VERSION

_PUBMED = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov", re.I)
_DOI = re.compile(r"\b10\.\d{4,9}/\S+", re.I)

_MAX_ITEMS = 72
_EXCERPT_CHARS = 720


def _paperish(ci: Any) -> bool:
    t = ((ci.title or "") + " " + (ci.link or "") + " " + (ci.snippet or ""))[:8000]
    return bool(_PUBMED.search(t) or _DOI.search(t))


def fingerprint_for_item_ids(item_ids: list[int]) -> str:
    """Include prompt version so digest rebuilds after prompt/normalization changes (not only item set)."""

    if not item_ids:
        raw = f"{PIPELINE_SEMVER}|v{PROMPT_VERSION}|empty"
    else:
        raw = f"{PIPELINE_SEMVER}|v{PROMPT_VERSION}|" + "|".join(str(i) for i in sorted(int(x) for x in item_ids))
    return sha256(raw.encode()).hexdigest()[:64]


def _sort_items_for_prompt(items: list[Any]) -> list[Any]:
    paper = [x for x in items if _paperish(x)]
    other = [x for x in items if not _paperish(x)]
    return paper + other


def _format_evidence_block(items: list[Any]) -> tuple[str, list[int]]:
    blocks: list[str] = []
    ids: list[int] = []
    for ci in items[:_MAX_ITEMS]:
        ids.append(int(ci.id))
        sn = plaintext_excerpt((ci.snippet or ""), _EXCERPT_CHARS).strip()
        blocks.append(
            f"CONTENT_ITEM_ID={ci.id}\n"
            f"title={(ci.title or '').strip()}\n"
            f"link={(ci.link or '').strip()}\n"
            f"snippet={sn}"
        )
    return "\n\n---\n\n".join(blocks), ids


def latest_ok_digest_for_person(person_id: int) -> PublicActivityDigest | None:
    return (
        PublicActivityDigest.query.filter_by(person_id=int(person_id), status="ok")
        .order_by(desc(PublicActivityDigest.completed_at), desc(PublicActivityDigest.id))
        .first()
    )


def latest_ok_digest_for_organization(organization_id: int) -> PublicActivityDigest | None:
    return (
        PublicActivityDigest.query.filter_by(organization_id=int(organization_id), status="ok")
        .order_by(desc(PublicActivityDigest.completed_at), desc(PublicActivityDigest.id))
        .first()
    )


_RECENT_HEADING_ONLY = re.compile(r"^[\s*_`]*recent activity[\s*_`:]*$", re.I)
_OVERFLOW_PHRASE = re.compile(
    r"(?is)(additional\s+items?\s+exist|additional\s+information:)",
)


def _rewrite_overflow_closing(line: str) -> str | None:
    """Map legacy closing lines to the canonical plain-text pattern (no leading '- ')."""

    stripped = line.strip()
    if stripped.startswith("- "):
        stripped = stripped[2:].strip()
    lo = stripped.lower()
    looks_overflow = (
        _OVERFLOW_PHRASE.search(stripped) is not None
        or "beyond this summary" in lo
        or ("additional information" in lo and re.search(r"\d+", stripped))
    )
    if not looks_overflow:
        return None
    mnum = re.search(r"\b(\d+)\b", stripped)
    if mnum:
        return f"Beyond these highlights, {mnum.group(1)} more items appear in approved sources."
    return "Beyond these highlights, additional items appear in approved sources."


def normalize_public_digest_summary(text: str) -> str:
    """Strip markdown habits and normalize bullets so public plain-text display stays consistent."""

    if not text:
        return ""
    s = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    while True:
        nxt = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        nxt = re.sub(r"__([^_]+)__", r"\1", nxt)
        if nxt == s:
            break
        s = nxt
    s = s.replace("**", "").replace("__", "")

    lines_out: list[str] = []
    for raw in s.split("\n"):
        if not raw.strip():
            if lines_out and lines_out[-1] != "":
                lines_out.append("")
            continue

        line = raw.strip()
        line = re.sub(r"^#{1,6}\s+", "", line)
        if line.startswith("> "):
            line = line[2:].strip()

        if _RECENT_HEADING_ONLY.match(line):
            continue

        line = re.sub(r"^[\s*_`]*recent activity[\s*_`]*\s*", "", line, count=1, flags=re.I).strip()
        if not line:
            continue

        m_star_bullet = re.match(r"^\*\s+(\S.*)$", line)
        if m_star_bullet:
            line = "- " + m_star_bullet.group(1).strip()
        elif line.startswith("+ "):
            line = "- " + line[2:].lstrip()
        elif re.match(r"^\+\s+\S", line):
            line = "- " + re.sub(r"^\+\s+", "", line, count=1).strip()
        elif len(line) >= 2 and line[0] in ("\u2022", "\u2013", "\u2014") and line[1] in " \t":
            line = "- " + line[1:].lstrip()

        overflow = _rewrite_overflow_closing(line)
        if overflow is not None:
            line = overflow

        lines_out.append(line)

    joined = "\n".join(lines_out)
    while "\n\n\n" in joined:
        joined = joined.replace("\n\n\n", "\n\n")
    return joined.strip()


def _sanitize_cited(raw: Any, *, allowed: set[int]) -> list[int]:
    out: list[int] = []
    if not isinstance(raw, list):
        return out
    for x in raw:
        try:
            n = int(x)
        except (TypeError, ValueError):
            continue
        if n in allowed:
            out.append(n)
    return sorted(set(out))[:24]


def build_public_digest_for_person(person_id: int, *, commit: bool = True) -> dict[str, Any]:
    from datetime import datetime, timezone

    pid = int(person_id)
    p = db.session.get(Person, pid)
    if p is None:
        return {"status": "error", "detail": "person not found", "digest_id": None}

    items = _sort_items_for_prompt(public_content_items_for_person(pid, limit=_MAX_ITEMS))
    block, item_ids = _format_evidence_block(items)
    fp = fingerprint_for_item_ids(item_ids)

    prev = latest_ok_digest_for_person(pid)
    if prev and (prev.input_fingerprint or "") == fp:
        p.public_digest_stale = False
        if commit:
            db.session.commit()
        return {"status": "skipped", "detail": "fingerprint unchanged", "digest_id": prev.id}

    if not item_ids:
        summary = "No recent public activity from approved sources."
        row = PublicActivityDigest(
            person_id=pid,
            organization_id=None,
            summary_text=summary,
            cited_content_item_ids_json=json.dumps([], ensure_ascii=False),
            input_fingerprint=fp,
            prompt_version=PROMPT_VERSION,
            model_used=None,
            status="ok",
            error_detail=None,
            completed_at=datetime.now(timezone.utc),
        )
        db.session.add(row)
        p.public_digest_stale = False
        if commit:
            db.session.commit()
        return {"status": "ok", "detail": summary, "digest_id": row.id}

    tmpl = (prompts_dir() / "public_digest_person.txt").read_text(encoding="utf-8")
    prompt = tmpl.replace("{{EVIDENCE_BLOCK}}", block).replace("{{ENTITY_NAME}}", (p.display_name or "").strip())
    parsed = run_public_digest_llm(prompt)
    allowed = set(item_ids)

    if not isinstance(parsed, dict):
        row = PublicActivityDigest(
            person_id=pid,
            organization_id=None,
            summary_text=None,
            cited_content_item_ids_json=None,
            input_fingerprint=fp,
            prompt_version=PROMPT_VERSION,
            model_used=OLLAMA_MODEL,
            status="failed",
            error_detail="Model did not return valid JSON.",
            completed_at=datetime.now(timezone.utc),
        )
        db.session.add(row)
        if commit:
            db.session.commit()
        return {"status": "failed", "detail": row.error_detail, "digest_id": row.id}

    summary = normalize_public_digest_summary((parsed.get("summary") or "").strip()) or "(empty summary)"
    cited = _sanitize_cited(parsed.get("cited_content_item_ids"), allowed=allowed)
    row = PublicActivityDigest(
        person_id=pid,
        organization_id=None,
        summary_text=summary,
        cited_content_item_ids_json=json.dumps(cited, ensure_ascii=False),
        input_fingerprint=fp,
        prompt_version=PROMPT_VERSION,
        model_used=OLLAMA_MODEL,
        status="ok",
        error_detail=None,
        completed_at=datetime.now(timezone.utc),
    )
    db.session.add(row)
    p.public_digest_stale = False
    if commit:
        db.session.commit()
    return {"status": "ok", "detail": "built", "digest_id": row.id}


def build_public_digest_for_organization(organization_id: int, *, commit: bool = True) -> dict[str, Any]:
    from datetime import datetime, timezone

    oid = int(organization_id)
    o = db.session.get(Organization, oid)
    if o is None:
        return {"status": "error", "detail": "organization not found", "digest_id": None}

    items = _sort_items_for_prompt(public_content_items_for_organization(oid, limit=_MAX_ITEMS))
    block, item_ids = _format_evidence_block(items)
    fp = fingerprint_for_item_ids(item_ids)

    prev = latest_ok_digest_for_organization(oid)
    if prev and (prev.input_fingerprint or "") == fp:
        o.public_digest_stale = False
        if commit:
            db.session.commit()
        return {"status": "skipped", "detail": "fingerprint unchanged", "digest_id": prev.id}

    if not item_ids:
        summary = "No recent public activity from approved sources."
        row = PublicActivityDigest(
            person_id=None,
            organization_id=oid,
            summary_text=summary,
            cited_content_item_ids_json=json.dumps([], ensure_ascii=False),
            input_fingerprint=fp,
            prompt_version=PROMPT_VERSION,
            model_used=None,
            status="ok",
            error_detail=None,
            completed_at=datetime.now(timezone.utc),
        )
        db.session.add(row)
        o.public_digest_stale = False
        if commit:
            db.session.commit()
        return {"status": "ok", "detail": summary, "digest_id": row.id}

    tmpl = (prompts_dir() / "public_digest_organization.txt").read_text(encoding="utf-8")
    prompt = tmpl.replace("{{EVIDENCE_BLOCK}}", block).replace("{{ENTITY_NAME}}", (o.display_name or "").strip())
    parsed = run_public_digest_llm(prompt)
    allowed = set(item_ids)

    if not isinstance(parsed, dict):
        row = PublicActivityDigest(
            person_id=None,
            organization_id=oid,
            summary_text=None,
            cited_content_item_ids_json=None,
            input_fingerprint=fp,
            prompt_version=PROMPT_VERSION,
            model_used=OLLAMA_MODEL,
            status="failed",
            error_detail="Model did not return valid JSON.",
            completed_at=datetime.now(timezone.utc),
        )
        db.session.add(row)
        if commit:
            db.session.commit()
        return {"status": "failed", "detail": row.error_detail, "digest_id": row.id}

    summary = normalize_public_digest_summary((parsed.get("summary") or "").strip()) or "(empty summary)"
    cited = _sanitize_cited(parsed.get("cited_content_item_ids"), allowed=allowed)
    row = PublicActivityDigest(
        person_id=None,
        organization_id=oid,
        summary_text=summary,
        cited_content_item_ids_json=json.dumps(cited, ensure_ascii=False),
        input_fingerprint=fp,
        prompt_version=PROMPT_VERSION,
        model_used=OLLAMA_MODEL,
        status="ok",
        error_detail=None,
        completed_at=datetime.now(timezone.utc),
    )
    db.session.add(row)
    o.public_digest_stale = False
    if commit:
        db.session.commit()
    return {"status": "ok", "detail": "built", "digest_id": row.id}


def build_all_stale_public_digests(*, commit: bool = True) -> dict[str, Any]:
    """Process every person/org flagged ``public_digest_stale``."""

    people = Person.query.filter(Person.public_digest_stale.is_(True)).order_by(Person.id).all()
    orgs = Organization.query.filter(Organization.public_digest_stale.is_(True)).order_by(Organization.id).all()
    results: list[dict[str, Any]] = []
    for p in people:
        results.append({"kind": "person", "id": p.id, **build_public_digest_for_person(p.id, commit=commit)})
    for o in orgs:
        results.append({"kind": "organization", "id": o.id, **build_public_digest_for_organization(o.id, commit=commit)})
    return {"processed": len(results), "results": results}
