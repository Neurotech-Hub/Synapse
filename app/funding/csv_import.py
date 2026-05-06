from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.extensions import db
from app.funding.effort import EffortClassification, apply_effort_classification, classify_effort_heuristic, score_for_effort
from app.ingest.urlnorm import UrlValidationError, canonical_url, stable_catalog_url
from app.models import FundingOpportunity

ALLOWED_EFFORT = {"mild", "moderate", "heavy", "unknown"}
ALLOWED_STATUS = {"draft", "active", "expired", "archived"}
ALLOWED_VISIBILITY = {"public", "private"}
ALLOWED_SOURCE_TYPES = {"manual", "csv", "imported", "url_fetch", "fetched_url", "rss", "public_search"}

CSV_COLUMNS = [
    "external_id",
    "title",
    "sponsor_name",
    "source_url",
    "source_type",
    "status",
    "visibility",
    "deadline_date",
    "deadline_text",
    "amount_min",
    "amount_max",
    "amount_text",
    "mechanism",
    "effort_index_override",
    "topic_tags",
    "method_tags",
    "eligibility_summary",
    "notes_private",
    "raw_text",
]


@dataclass
class FundingImportRowResult:
    row_number: int
    title: str | None = None
    action: str = "skip"
    funding_id: int | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class FundingImportSummary:
    dry_run: bool
    total_rows: int = 0
    valid_rows: int = 0
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    results: list[FundingImportRowResult] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(len(row.errors) for row in self.results)


def parse_funding_csv(
    payload: bytes | str,
    *,
    commit: bool = False,
    update_existing: bool = False,
) -> FundingImportSummary:
    """Validate a funding CSV and optionally commit valid rows."""

    text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else str(payload)
    reader = csv.DictReader(io.StringIO(text))
    summary = FundingImportSummary(dry_run=not commit)
    seen_external_ids: set[str] = set()
    seen_urls: set[str] = set()

    if reader.fieldnames is None:
        summary.results.append(FundingImportRowResult(row_number=1, errors=["CSV is empty or missing a header row."]))
        return summary

    unknown_columns = sorted({str(name).strip() for name in reader.fieldnames if name} - set(CSV_COLUMNS))
    if unknown_columns:
        summary.results.append(
            FundingImportRowResult(
                row_number=1,
                errors=[f"Unknown column(s): {', '.join(unknown_columns)}."],
            )
        )
        return summary

    for row_number, raw_row in enumerate(reader, start=2):
        summary.total_rows += 1
        result = FundingImportRowResult(row_number=row_number)
        normalized = _normalize_row(raw_row)
        result.title = normalized.get("title")
        _validate_row(normalized, result)

        external_id = normalized.get("external_id")
        normalized_url = normalized.get("normalized_source_url")
        if external_id:
            if external_id in seen_external_ids:
                result.errors.append(f"Duplicate external_id in CSV: {external_id}.")
            seen_external_ids.add(external_id)
        if normalized_url:
            if normalized_url in seen_urls:
                result.errors.append(f"Duplicate source_url in CSV: {normalized_url}.")
            seen_urls.add(normalized_url)

        existing = None
        if not result.errors:
            existing = _find_existing(external_id=external_id, normalized_source_url=normalized_url)
            if existing is not None and not update_existing:
                result.errors.append("Duplicate existing funding opportunity; enable update-on-duplicate to update it.")

        if result.errors:
            summary.skipped_count += 1
            summary.results.append(result)
            continue

        summary.valid_rows += 1
        if existing is not None:
            result.action = "update"
        else:
            result.action = "create"

        if commit:
            target = existing or FundingOpportunity(slug=allocate_funding_slug(normalized.get("title") or external_id or "funding"))
            _apply_row(target, normalized)
            db.session.add(target)
            db.session.flush()
            result.funding_id = target.id
            if existing is None:
                summary.created_count += 1
            else:
                summary.updated_count += 1

        summary.results.append(result)

    if commit:
        db.session.commit()

    return summary


def parse_tag_string(raw: str | None) -> list[str]:
    values: list[str] = []
    for part in (raw or "").split(";"):
        tag = " ".join(part.strip().split())
        if tag and tag not in values:
            values.append(tag)
    return values


def effort_score_for_index(effort_index: str | None) -> float | None:
    return score_for_effort(effort_index)


def normalize_visibility(raw: str | None) -> bool:
    return (raw or "private").strip().lower() == "public"


def normalize_source_url(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    canonical_url(raw)
    return stable_catalog_url(raw)


def _normalize_row(raw_row: dict[str, Any]) -> dict[str, Any]:
    row = {key: _blank_to_none(value) for key, value in raw_row.items() if key is not None}
    row["status"] = (row.get("status") or "draft").lower()
    row["source_type"] = (row.get("source_type") or "csv").lower()
    row["visibility"] = (row.get("visibility") or "private").lower()
    row["effort_index"] = (row.get("effort_index_override") or "unknown").lower()
    row["topic_tags_json"] = parse_tag_string(row.get("topic_tags"))
    row["method_tags_json"] = parse_tag_string(row.get("method_tags"))

    try:
        row["normalized_source_url"] = normalize_source_url(row.get("source_url"))
    except UrlValidationError as exc:
        row["normalized_source_url"] = None
        row.setdefault("_errors", []).append(f"Invalid source_url: {exc}")

    for key in ("amount_min", "amount_max"):
        row[key] = _parse_int(row.get(key), key=key, errors=row.setdefault("_errors", []))

    row["deadline_date"] = _parse_date(row.get("deadline_date"), errors=row.setdefault("_errors", []))
    return row


def _validate_row(row: dict[str, Any], result: FundingImportRowResult) -> None:
    result.errors.extend(row.get("_errors") or [])
    if not row.get("title"):
        result.errors.append("Missing required title.")
    if not row.get("source_url") and not row.get("external_id"):
        result.errors.append("Missing required source_url or external_id.")
    if row.get("status") not in ALLOWED_STATUS:
        result.errors.append(f"Invalid status: {row.get('status')}.")
    if row.get("visibility") not in ALLOWED_VISIBILITY:
        result.errors.append(f"Invalid visibility: {row.get('visibility')}.")
    if row.get("source_type") not in ALLOWED_SOURCE_TYPES:
        result.errors.append(f"Invalid source_type: {row.get('source_type')}.")
    if row.get("effort_index") not in ALLOWED_EFFORT:
        result.errors.append(f"Invalid effort_index_override: {row.get('effort_index')}.")


def _apply_row(target: FundingOpportunity, row: dict[str, Any]) -> None:
    target.external_id = row.get("external_id")
    target.title = row.get("title") or target.title
    target.sponsor_name = row.get("sponsor_name")
    target.source_url = row.get("source_url")
    target.normalized_source_url = row.get("normalized_source_url")
    target.source_type = row.get("source_type") or "csv"
    target.status = row.get("status") or "draft"
    target.is_public = normalize_visibility(row.get("visibility"))
    target.deadline_date = row.get("deadline_date")
    target.deadline_text = row.get("deadline_text")
    target.amount_min = row.get("amount_min")
    target.amount_max = row.get("amount_max")
    target.amount_text = row.get("amount_text")
    target.mechanism = row.get("mechanism")
    if row.get("effort_index_override"):
        effort_index = row.get("effort_index") or "unknown"
        apply_effort_classification(
            target,
            EffortClassification(
                effort_index=effort_index,
                effort_score=effort_score_for_index(effort_index),
                confidence=1.0 if effort_index != "unknown" else 0.6,
                rationale="Effort index was provided by CSV import override.",
                signals=["csv effort_index_override"],
            ),
        )
    else:
        apply_effort_classification(target, classify_effort_heuristic(target))
    target.eligibility_summary = row.get("eligibility_summary")
    target.notes_private = row.get("notes_private")
    target.raw_text = row.get("raw_text")
    target.topic_tags_json = row.get("topic_tags_json") or []
    target.method_tags_json = row.get("method_tags_json") or []


def _find_existing(*, external_id: str | None, normalized_source_url: str | None) -> FundingOpportunity | None:
    if external_id:
        existing = FundingOpportunity.query.filter_by(external_id=external_id).first()
        if existing is not None:
            return existing
    if normalized_source_url:
        return FundingOpportunity.query.filter_by(normalized_source_url=normalized_source_url).first()
    return None


def allocate_funding_slug(title: str, *, exclude_id: int | None = None) -> str:
    base = _slug_base(title) or "funding"
    base = base[:180].strip("-_") or "funding"
    candidate = base
    suffix = 2
    while True:
        query = FundingOpportunity.query.filter_by(slug=candidate)
        if exclude_id is not None:
            query = query.filter(FundingOpportunity.id != exclude_id)
        if query.first() is None:
            return candidate
        extra = f"_{suffix}"
        candidate = f"{base[: 180 - len(extra)]}{extra}"
        suffix += 1


def _slug_base(raw: str | None) -> str:
    if raw is None:
        return ""
    slug = str(raw).strip().lower().replace(" ", "_")
    slug = re.sub(r"[^a-z0-9_-]+", "", slug)
    slug = re.sub(r"_+", "_", slug)
    return slug.strip("_-")


def _blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_int(raw: str | None, *, key: str, errors: list[str]) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "")
    try:
        value = int(text)
    except ValueError:
        errors.append(f"Invalid {key}: {raw}.")
        return None
    if value < 0:
        errors.append(f"Invalid {key}: must be non-negative.")
        return None
    return value


def _parse_date(raw: str | None, *, errors: list[str]):
    if raw is None:
        return None
    try:
        return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
    except ValueError:
        errors.append(f"Invalid deadline_date: {raw}. Use YYYY-MM-DD.")
        return None
