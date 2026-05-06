from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.extensions import db
from app.models import FundingOpportunity


@dataclass(frozen=True)
class FieldDiff:
    field: str
    label: str
    current_value: Any
    draft_value: Any
    status: str
    is_manual: bool
    can_apply: bool


FIELD_MAP: dict[str, tuple[str, str, str]] = {
    "title": ("Title", "title", "title"),
    "sponsor_name": ("Sponsor", "sponsor_name", "sponsor_name"),
    "summary_public": ("Public summary", "summary_public", "public_summary"),
    "summary_private": ("Private summary", "summary_private", "private_summary"),
    "eligibility_summary": ("Eligibility", "eligibility_summary", "eligibility_summary"),
    "amount_text": ("Amount", "amount_text", "amount_text"),
    "deadline_text": ("Deadline text", "deadline_text", "deadline_text"),
    "deadline_date": ("Deadline date", "deadline_date", "deadline_date"),
    "topic_tags_json": ("Topic tags", "topic_tags_json", "topic_tags"),
    "method_tags_json": ("Method tags", "method_tags_json", "method_tags"),
    "hub_relevance_json": ("Hub relevance", "hub_relevance_json", "possible_hub_relevance"),
}


def get_funding_synthesis_diff(funding: FundingOpportunity) -> list[FieldDiff]:
    draft = funding.synthesized_json or {}
    rows: list[FieldDiff] = []
    for field, (label, model_field, draft_field) in FIELD_MAP.items():
        current = getattr(funding, model_field)
        draft_value = _normalize_for_field(field, draft.get(draft_field))
        current_value = _normalize_for_field(field, current)
        status = _status(current_value, draft_value)
        rows.append(
            FieldDiff(
                field=field,
                label=label,
                current_value=current_value,
                draft_value=draft_value,
                status=status,
                is_manual=_has_value(current_value),
                can_apply=status in {"new", "changed"},
            )
        )
    return rows


def apply_funding_synthesis_fields(funding: FundingOpportunity, selected_fields: list[str]) -> list[str]:
    draft = funding.synthesized_json or {}
    changed: list[str] = []
    allowed = set(selected_fields or [])
    for field, (_label, model_field, draft_field) in FIELD_MAP.items():
        if field not in allowed:
            continue
        value = _normalize_for_field(field, draft.get(draft_field))
        if not _has_value(value):
            continue
        setattr(funding, model_field, value)
        changed.append(field)
    if changed:
        funding.synthesis_status = "synthesized"
        payload = dict(funding.synthesized_json or {})
        payload["applied_fields"] = sorted(set((payload.get("applied_fields") or []) + changed))
        payload["applied_at"] = datetime.now(timezone.utc).isoformat()
        funding.synthesized_json = payload
    db.session.commit()
    return changed


def _status(current: Any, draft: Any) -> str:
    if not _has_value(draft):
        return "missing"
    if not _has_value(current):
        return "new"
    if current == draft:
        return "unchanged"
    return "changed"


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _normalize_for_field(field: str, value: Any) -> Any:
    if field in {"topic_tags_json", "method_tags_json", "hub_relevance_json"}:
        return _dedupe_strings(value if isinstance(value, list) else ([value] if value else []))
    if field == "deadline_date":
        if value in (None, ""):
            return None
        if hasattr(value, "isoformat"):
            return value
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def _dedupe_strings(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        text = " ".join(str(value).strip().split())
        if text and text not in out:
            out.append(text)
    return out
