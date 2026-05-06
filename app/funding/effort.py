from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models import FundingOpportunity

EFFORT_SCORES = {"mild": 0.20, "moderate": 0.55, "heavy": 0.85}

HEAVY_TERMS = (
    "center",
    "consortium",
    "program project",
    "cooperative agreement",
    "multi-site",
    "institutional commitment",
    "training program",
    "large-scale",
    "infrastructure",
    "major instrumentation",
    "commercialization",
    "management plan",
    "cost sharing",
    "multi-pi",
    "multi investigator",
    "multiple institutions",
)

MODERATE_TERMS = (
    "research grant",
    "pilot project",
    "exploratory award",
    "technology development",
    "foundation award",
    "equipment award",
    "collaborative project",
    "budget justification",
    "letters of support",
    "preliminary data",
)

MILD_TERMS = (
    "seed grant",
    "mini grant",
    "travel award",
    "workshop award",
    "supplement",
    "voucher",
    "microgrant",
    "concept note",
    "letter of intent only",
    "rapid pilot",
    "internal pilot",
    "rolling review",
    "short application",
    "one-page proposal",
)


@dataclass
class EffortClassification:
    effort_index: str
    effort_score: float | None
    confidence: float | None
    rationale: str
    signals: list[str] = field(default_factory=list)


def score_for_effort(effort_index: str | None) -> float | None:
    return EFFORT_SCORES.get((effort_index or "").strip().lower())


def classify_effort_heuristic(funding: FundingOpportunity) -> EffortClassification:
    """Classify likely submission burden from lightweight structured fields and notes."""

    text = _combined_text(funding)
    signals: list[str] = []
    evidence_count = 0
    burden_score = 0.5

    if not text and funding.amount_max is None and not funding.mechanism:
        return EffortClassification(
            effort_index="unknown",
            effort_score=None,
            confidence=0.2,
            rationale="Not enough funding detail is available to estimate submission burden.",
            signals=["insufficient evidence"],
        )

    heavy_hits = _term_hits(text, HEAVY_TERMS)
    moderate_hits = _term_hits(text, MODERATE_TERMS)
    mild_hits = _term_hits(text, MILD_TERMS)

    if heavy_hits:
        evidence_count += 1
        burden_score += min(0.35, 0.16 * len(heavy_hits))
        signals.append(f"heavy mechanism/application language: {', '.join(heavy_hits[:3])}")
    if moderate_hits:
        evidence_count += 1
        burden_score += min(0.14, 0.06 * len(moderate_hits))
        signals.append(f"moderate proposal language: {', '.join(moderate_hits[:3])}")
    if mild_hits:
        evidence_count += 1
        burden_score -= min(0.30, 0.12 * len(mild_hits))
        signals.append(f"streamlined mechanism language: {', '.join(mild_hits[:3])}")

    amount_signal = _amount_signal(funding.amount_max)
    if amount_signal:
        evidence_count += 1
        burden_score += amount_signal[0]
        signals.append(amount_signal[1])

    if funding.deadline_text and "loi" in funding.deadline_text.lower() and "full" in funding.deadline_text.lower():
        evidence_count += 1
        burden_score += 0.10
        signals.append("deadline text suggests LOI plus full proposal")

    if evidence_count == 0:
        return EffortClassification(
            effort_index="unknown",
            effort_score=None,
            confidence=0.3,
            rationale="Available fields do not include amount, mechanism, or application complexity signals.",
            signals=["no clear effort signals"],
        )

    burden_score = min(max(burden_score, 0.0), 1.0)
    if burden_score >= 0.75:
        label = "heavy"
    elif burden_score >= 0.40:
        label = "moderate"
    else:
        label = "mild"

    confidence = min(0.95, 0.45 + 0.12 * evidence_count + _signal_strength(label, heavy_hits, moderate_hits, mild_hits))
    rationale = _rationale(label, signals)
    return EffortClassification(
        effort_index=label,
        effort_score=score_for_effort(label),
        confidence=round(confidence, 2),
        rationale=rationale,
        signals=signals,
    )


def apply_effort_classification(funding: FundingOpportunity, classification: EffortClassification) -> None:
    funding.effort_index = classification.effort_index
    funding.effort_score = classification.effort_score
    funding.effort_confidence = classification.confidence
    funding.effort_rationale = classification.rationale
    funding.effort_signals_json = classification.signals


def _combined_text(funding: FundingOpportunity) -> str:
    parts = [
        funding.title,
        funding.sponsor_name,
        funding.amount_text,
        funding.mechanism,
        funding.deadline_text,
        funding.eligibility_summary,
        funding.notes_private,
        funding.raw_text,
        " ".join(funding.topic_tags_json or []),
        " ".join(funding.method_tags_json or []),
    ]
    return re.sub(r"\s+", " ", " ".join(p for p in parts if p).lower()).strip()


def _term_hits(text: str, terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if term in text]


def _amount_signal(amount_max: int | None) -> tuple[float, str] | None:
    if amount_max is None:
        return None
    if amount_max > 1_500_000:
        return (0.32, "large award amount above $1.5M")
    if amount_max >= 500_000:
        return (0.18, "substantial award amount between $500k and $1.5M")
    if amount_max >= 150_000:
        return (0.08, "mid-sized award amount between $150k and $500k")
    if amount_max <= 25_000:
        return (-0.24, "small award amount at or below $25k")
    if amount_max <= 150_000:
        return (-0.08, "small-to-mid award amount between $25k and $150k")
    return None


def _signal_strength(label: str, heavy_hits: list[str], moderate_hits: list[str], mild_hits: list[str]) -> float:
    if label == "heavy" and heavy_hits:
        return 0.12
    if label == "mild" and mild_hits:
        return 0.12
    if label == "moderate" and moderate_hits:
        return 0.08
    return 0.0


def _rationale(label: str, signals: list[str]) -> str:
    if label == "unknown":
        return "Not enough information is available to estimate submission burden."
    lead = {
        "mild": "Likely mild effort based on lightweight opportunity signals.",
        "moderate": "Likely moderate effort based on proposal or award-size signals.",
        "heavy": "Likely heavy effort based on major mechanism, team, or award-size signals.",
    }[label]
    if not signals:
        return lead
    return f"{lead} Signals: {'; '.join(signals[:3])}."
