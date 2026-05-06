from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.extensions import db
from app.funding.effort import EffortClassification, apply_effort_classification, classify_effort_heuristic, score_for_effort
from app.llm.execute import LLMExecutionResult, execute_prompt
from app.models import FundingOpportunity
from app.funding.synthesis_review import apply_funding_synthesis_fields


def synthesize_funding_from_raw_text(
    funding: FundingOpportunity,
    *,
    provider: str | None = None,
    allow_openai: bool = False,
    mock_provider=None,
) -> LLMExecutionResult:
    variables = {
        "source_url": funding.source_url_final or funding.source_url or "",
        "page_title": funding.title or "",
        "optional_admin_notes": funding.notes_private or "",
        "cleaned_text": (funding.raw_text or "")[:24_000],
        "schema": {
            "schema_version": "1.0",
            "title": "",
            "public_summary": "",
            "eligibility_summary": "",
            "amount_text": "",
            "deadline_text": "",
            "deadline_date": None,
            "topic_tags": [],
            "method_tags": [],
            "confidence": 0.0,
            "missing_information": [],
            "warnings": [],
        },
    }
    result = execute_prompt(
        "funding_extract",
        variables,
        provider=provider,
        source_type="funding",
        source_id=funding.id,
        allow_openai=allow_openai,
        mock_provider=mock_provider,
    )
    if result.run is not None:
        funding.synthesis_provider = result.run.provider
        funding.synthesis_model = result.run.model_name
        funding.synthesis_fingerprint = result.run.input_fingerprint
    if result.ok and result.data:
        funding.synthesized_json = result.data
        funding.synthesis_confidence = _float_or_none(result.data.get("confidence"))
        funding.synthesis_status = "needs_review"
        funding.synthesis_generated_at = datetime.now(timezone.utc)
        funding.synthesis_error = None
    else:
        funding.synthesis_status = "failed"
        funding.synthesis_error = "; ".join(result.errors) if result.errors else "Funding synthesis failed."
    db.session.commit()
    return result


def regenerate_funding_public_card(
    funding: FundingOpportunity,
    *,
    provider: str | None = None,
    allow_openai: bool = False,
    mock_provider=None,
) -> LLMExecutionResult:
    variables = {
        "funding_json": {
            "title": funding.title,
            "sponsor_name": funding.sponsor_name,
            "summary_public": funding.summary_public,
            "eligibility_summary": funding.eligibility_summary,
            "amount_text": funding.amount_text,
            "deadline_text": funding.deadline_text,
            "effort_index": funding.effort_index,
            "topic_tags": funding.topic_tags_json or [],
            "method_tags": funding.method_tags_json or [],
        },
        "schema": {
            "schema_version": "1.0",
            "display_title": "",
            "short_summary": "",
            "effort_label": "mild|moderate|heavy|unknown",
            "tags": [],
            "confidence": 0.0,
            "warnings": [],
        },
    }
    result = execute_prompt(
        "funding_public_card",
        variables,
        provider=provider,
        source_type="funding",
        source_id=funding.id,
        allow_openai=allow_openai,
        mock_provider=mock_provider,
    )
    payload = dict(funding.synthesized_json or {})
    if result.run is not None:
        funding.synthesis_provider = result.run.provider
        funding.synthesis_model = result.run.model_name
        funding.synthesis_fingerprint = result.run.input_fingerprint
    if result.ok and result.data:
        payload["public_card"] = result.data
        payload["public_card_status"] = "needs_review"
        funding.synthesized_json = payload
        funding.synthesis_status = "needs_review"
        funding.synthesis_generated_at = datetime.now(timezone.utc)
        funding.synthesis_error = None
    else:
        funding.synthesis_status = "failed"
        funding.synthesis_error = "; ".join(result.errors) if result.errors else "Public-card regeneration failed."
    db.session.commit()
    return result


def apply_funding_public_card(funding: FundingOpportunity) -> list[str]:
    card = (funding.synthesized_json or {}).get("public_card") or {}
    draft = dict(funding.synthesized_json or {})
    if card.get("short_summary"):
        draft["public_summary"] = card.get("short_summary")
    if card.get("tags") and isinstance(card.get("tags"), list):
        draft["topic_tags"] = card.get("tags")
    funding.synthesized_json = draft
    return apply_funding_synthesis_fields(funding, ["summary_public", "topic_tags_json"])


def apply_funding_synthesis_draft(funding: FundingOpportunity, *, fields: list[str] | None = None) -> list[str]:
    return apply_funding_synthesis_fields(
        funding,
        fields
        or [
            "title",
            "sponsor_name",
            "summary_public",
            "summary_private",
            "eligibility_summary",
            "amount_text",
            "deadline_text",
            "deadline_date",
            "topic_tags_json",
            "method_tags_json",
            "hub_relevance_json",
        ],
    )


def discard_funding_synthesis_draft(funding: FundingOpportunity) -> None:
    funding.synthesis_status = "not_started" if not funding.raw_text else "fetched"
    funding.synthesized_json = None
    funding.synthesis_error = None
    db.session.commit()


def reclassify_effort_from_synthesis(funding: FundingOpportunity) -> None:
    draft = funding.synthesized_json or {}
    effort = str(draft.get("effort_index") or "").strip().lower()
    if effort in {"mild", "moderate", "heavy", "unknown"}:
        apply_effort_classification(
            funding,
            EffortClassification(
                effort_index=effort,
                effort_score=score_for_effort(effort),
                confidence=_float_or_none(draft.get("confidence")),
                rationale=str(draft.get("effort_rationale") or "Effort came from funding synthesis draft."),
                signals=["funding synthesis draft"],
            ),
        )
    else:
        apply_effort_classification(funding, classify_effort_heuristic(funding))
    db.session.commit()


def _dedupe_strings(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        text = " ".join(str(value).strip().split())
        if text and text not in out:
            out.append(text)
    return out


def _float_or_none(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
