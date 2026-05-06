from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.extensions import db
from app.llm.execute import LLMExecutionResult, execute_prompt
from app.models import CollaborationHypothesis, FundingOpportunity, Idea, MatchEdge, MatchRun, Organization, Person

PIPELINE_VERSION = "deterministic_v1"


@dataclass
class CandidateScore:
    funding: FundingOpportunity
    idea: Idea
    score_total: float
    confidence: float
    topic_fit: float
    method_fit: float
    funding_fit: float
    evidence_strength: float
    recency: float
    strategic_value: float
    effort_reasonableness: float
    features: dict = field(default_factory=dict)
    evidence: list[dict] = field(default_factory=list)

    @property
    def rationale(self) -> str:
        shared = self.features.get("shared_terms") or []
        shared_text = ", ".join(shared[:5]) if shared else "keyword overlap"
        return (
            f"Funding opportunity may support this idea based on {shared_text}. "
            f"Effort is tracked separately as {self.features.get('funding_effort_index', 'unknown')}."
        )


def generate_funding_to_idea_matches(
    funding: FundingOpportunity,
    *,
    candidate_limit: int = 100,
    min_score: float = 0.35,
) -> MatchRun:
    run = MatchRun(
        run_type="funding_to_idea",
        source_type="funding",
        source_id=funding.id,
        status="running",
        pipeline_version=PIPELINE_VERSION,
        params_json={"candidate_limit": candidate_limit, "min_score": min_score},
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(run)
    db.session.flush()
    try:
        ideas = (
            Idea.query.filter(Idea.status != "archived")
            .filter(Idea.status != "hidden")
            .order_by(Idea.updated_at.desc(), Idea.id.desc())
            .limit(max(int(candidate_limit), 1))
            .all()
        )
        candidates = [score_funding_to_idea(funding, idea) for idea in ideas]
        candidates = [candidate for candidate in candidates if candidate.score_total >= min_score]
        candidates.sort(key=lambda candidate: candidate.score_total, reverse=True)

        created = 0
        updated = 0
        for candidate in candidates:
            edge, is_new = upsert_funding_to_idea_edge(candidate, run)
            if is_new:
                created += 1
            else:
                updated += 1
            db.session.add(edge)

        run.status = "ok"
        run.candidates_count = len(ideas)
        run.scored_count = len(candidates)
        run.result_summary_json = {"created": created, "updated": updated}
        run.finished_at = datetime.now(timezone.utc)
        db.session.commit()
        return run
    except Exception as exc:
        run.status = "failed"
        run.error_count = 1
        run.error_text = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.session.commit()
        raise


def generate_idea_to_funding_matches(
    idea: Idea,
    *,
    candidate_limit: int = 100,
    min_score: float = 0.35,
) -> MatchRun:
    run = MatchRun(
        run_type="idea_to_funding",
        source_type="idea",
        source_id=idea.id,
        status="running",
        pipeline_version=PIPELINE_VERSION,
        params_json={"candidate_limit": candidate_limit, "min_score": min_score},
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(run)
    db.session.flush()
    try:
        fundings = (
            FundingOpportunity.query.filter(FundingOpportunity.status != "archived")
            .order_by(FundingOpportunity.updated_at.desc(), FundingOpportunity.id.desc())
            .limit(max(int(candidate_limit), 1))
            .all()
        )
        candidates = [score_funding_to_idea(funding, idea) for funding in fundings]
        candidates = [candidate for candidate in candidates if candidate.score_total >= min_score]
        candidates.sort(key=lambda candidate: candidate.score_total, reverse=True)

        created = 0
        updated = 0
        for candidate in candidates:
            edge, is_new = upsert_funding_to_idea_edge(candidate, run)
            if is_new:
                created += 1
            else:
                updated += 1
            db.session.add(edge)

        run.status = "ok"
        run.candidates_count = len(fundings)
        run.scored_count = len(candidates)
        run.result_summary_json = {"created": created, "updated": updated}
        run.finished_at = datetime.now(timezone.utc)
        db.session.commit()
        return run
    except Exception as exc:
        run.status = "failed"
        run.error_count = 1
        run.error_text = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.session.commit()
        raise


def generate_person_to_idea_matches(person: Person, *, candidate_limit: int = 100, min_score: float = 0.30) -> MatchRun:
    return _generate_entity_to_idea_matches("person", person.id, _entity_terms_for_person(person), candidate_limit, min_score)


def generate_organization_to_idea_matches(
    organization: Organization, *, candidate_limit: int = 100, min_score: float = 0.30
) -> MatchRun:
    terms = set()
    persona = getattr(organization, "persona", None)
    if persona:
        terms |= _norm_set((persona.research_focus or []) + (persona.methods or []) + (persona.keywords or []))
    terms |= _keywords((organization.display_name or "") + " " + (organization.notes or ""))
    return _generate_entity_to_idea_matches("organization", organization.id, terms, candidate_limit, min_score)


def generate_funding_to_person_matches(
    funding: FundingOpportunity, *, candidate_limit: int = 100, min_score: float = 0.25
) -> MatchRun:
    return _generate_funding_to_entity_via_ideas(funding, "person", Person.query.limit(candidate_limit).all(), min_score)


def generate_funding_to_organization_matches(
    funding: FundingOpportunity, *, candidate_limit: int = 100, min_score: float = 0.25
) -> MatchRun:
    return _generate_funding_to_entity_via_ideas(
        funding, "organization", Organization.query.limit(candidate_limit).all(), min_score
    )


def create_manual_match_edge(
    *,
    source_type: str,
    source_id: int,
    target_type: str,
    target_id: int,
    match_type: str,
    rationale: str | None = None,
    visibility: str = "private",
) -> MatchEdge:
    edge = MatchEdge.query.filter_by(
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        match_type=match_type,
    ).first()
    if edge is None:
        edge = MatchEdge(source_type=source_type, source_id=source_id, target_type=target_type, target_id=target_id, match_type=match_type)
    edge.status = "accepted"
    edge.visibility = visibility if visibility in {"private", "public_safe", "public", "hidden"} else "private"
    edge.score_total = edge.score_total or 1.0
    edge.confidence = edge.confidence or 1.0
    edge.rationale = rationale or "Manual admin relationship."
    edge.private_rationale = edge.rationale
    edge.features_json = {**(edge.features_json or {}), "manual": True}
    edge.reviewed_at = datetime.now(timezone.utc)
    db.session.add(edge)
    db.session.commit()
    return edge


def update_match_edge_status(edge: MatchEdge, status: str) -> None:
    if status not in {"needs_review", "accepted", "rejected", "archived", "hidden", "stale"}:
        raise ValueError(f"Unsupported match status: {status}")
    edge.status = status
    if status in {"accepted", "rejected"}:
        edge.reviewed_at = datetime.now(timezone.utc)
    if status == "archived":
        edge.archived_at = datetime.now(timezone.utc)
    db.session.commit()


def update_match_edge_visibility(edge: MatchEdge, visibility: str) -> None:
    if visibility not in {"private", "public_safe", "public", "hidden"}:
        raise ValueError(f"Unsupported match visibility: {visibility}")
    edge.visibility = visibility
    db.session.commit()


def update_match_edge_note(edge: MatchEdge, *, private_rationale: str | None, public_rationale: str | None) -> None:
    edge.private_rationale = (private_rationale or "").strip() or None
    edge.public_rationale = (public_rationale or "").strip() or None
    edge.rationale = edge.private_rationale or edge.rationale
    db.session.commit()


def generate_match_rationale(
    edge: MatchEdge,
    *,
    provider: str | None = None,
    allow_openai: bool = False,
    mock_provider=None,
) -> LLMExecutionResult:
    variables = {
        "entity_snapshot": {
            "source_type": edge.source_type,
            "source_id": edge.source_id,
            "target_type": edge.target_type,
            "target_id": edge.target_id,
            "features": edge.features_json or {},
            "evidence": edge.evidence_json or [],
        },
        "idea_json": {
            "match_type": edge.match_type,
            "score_total": edge.score_total,
            "current_rationale": edge.rationale or edge.private_rationale or "",
        },
        "schema": {
            "schema_version": "1.0",
            "match_score": 0.0,
            "relationship_type": "direct|adjacent|weak|unknown",
            "rationale": "",
            "supporting_points": [],
            "confidence": 0.0,
            "warnings": [],
        },
    }
    result = execute_prompt(
        "match_entity_to_idea",
        variables,
        provider=provider,
        source_type="match_edge",
        source_id=edge.id,
        allow_openai=allow_openai,
        mock_provider=mock_provider,
    )
    if result.ok and result.data:
        edge.private_rationale = result.data.get("rationale") or edge.private_rationale
        edge.rationale = edge.private_rationale or edge.rationale
        points = result.data.get("supporting_points") or []
        warnings = result.data.get("warnings") or []
        edge.synthesized_json = {
            "llm_run_id": result.run.id if result.run else None,
            "relationship_type": result.data.get("relationship_type"),
            "supporting_points": points,
            "warnings": warnings,
            "confidence": result.data.get("confidence"),
        }
        if result.data.get("confidence") is not None:
            edge.confidence = result.data.get("confidence")
        if result.data.get("match_score") is not None:
            edge.score_total = result.data.get("match_score")
        if result.data.get("relationship_type") in {"direct", "adjacent"}:
            edge.public_rationale = "Related public research themes may connect these records."
        db.session.commit()
    return result


def score_funding_to_idea(funding: FundingOpportunity, idea: Idea) -> CandidateScore:
    funding_topics = _norm_set(funding.topic_tags_json or [])
    funding_methods = _norm_set(funding.method_tags_json or [])
    idea_tags = _norm_set((idea.tags_json or []) + (idea.aliases_json or []) + (idea.hub_capabilities_json or []))

    shared_topic = sorted(funding_topics & idea_tags)
    shared_method = sorted(funding_methods & idea_tags)
    funding_words = _keywords(
        " ".join(
            [
                funding.title or "",
                funding.sponsor_name or "",
                funding.mechanism or "",
                funding.summary_public or "",
                funding.eligibility_summary or "",
                " ".join(funding.topic_tags_json or []),
                " ".join(funding.method_tags_json or []),
            ]
        )
    )
    idea_words = _keywords(
        " ".join(
            [
                idea.title or "",
                idea.short_description or "",
                idea.public_summary or "",
                idea.hub_relevance or "",
                " ".join(idea.tags_json or []),
                " ".join(idea.aliases_json or []),
            ]
        )
    )
    shared_words = sorted(funding_words & idea_words)
    if not shared_topic and not shared_method and len(shared_words) < 2:
        return CandidateScore(
            funding=funding,
            idea=idea,
            score_total=0.0,
            confidence=0.2,
            topic_fit=0.0,
            method_fit=0.0,
            funding_fit=0.0,
            evidence_strength=0.0,
            recency=0.0,
            strategic_value=0.0,
            effort_reasonableness=0.0,
            features={
                "shared_topic_tags": [],
                "shared_method_tags": [],
                "shared_keywords": shared_words,
                "shared_terms": shared_words,
                "funding_status": funding.status,
                "funding_effort_index": funding.effort_index,
            },
            evidence=[],
        )

    topic_fit = min(1.0, 0.45 * len(shared_topic) + 0.12 * len(shared_words))
    method_fit = min(1.0, 0.50 * len(shared_method) + 0.08 * len(shared_words))
    funding_fit = 0.75 if funding.status == "active" else 0.45 if funding.status == "draft" else 0.25
    evidence_strength = min(1.0, 0.30 + 0.18 * (len(shared_topic) + len(shared_method)) + 0.04 * len(shared_words))
    recency = 0.60
    strategic_value = 0.75 if set(idea.quality_flags_json or []) & {"high_public_value", "high_hub_relevance"} else 0.55
    effort_reasonableness = {"mild": 0.85, "moderate": 0.80, "heavy": 0.65, "unknown": 0.45}.get(
        funding.effort_index or "unknown",
        0.45,
    )
    score_total = (
        0.25 * topic_fit
        + 0.20 * method_fit
        + 0.15 * funding_fit
        + 0.15 * funding_fit
        + 0.10 * recency
        + 0.10 * evidence_strength
        + 0.05 * effort_reasonableness
    )
    confidence = min(0.95, 0.35 + 0.12 * len(shared_topic) + 0.12 * len(shared_method) + 0.03 * len(shared_words))
    shared_terms = sorted(set(shared_topic + shared_method + shared_words))
    features = {
        "shared_topic_tags": shared_topic,
        "shared_method_tags": shared_method,
        "shared_keywords": shared_words[:12],
        "shared_terms": shared_terms,
        "funding_status": funding.status,
        "funding_effort_index": funding.effort_index,
        "weights": {
            "topic_fit": 0.25,
            "method_fit": 0.20,
            "eligibility_fit": 0.15,
            "funding_relevance": 0.15,
            "deadline_urgency": 0.10,
            "evidence_strength": 0.10,
            "effort_reasonableness": 0.05,
        },
    }
    evidence = [
        {
            "kind": "funding_summary",
            "entity_type": "funding",
            "entity_id": funding.id,
            "title": funding.title,
            "excerpt": funding.summary_public or funding.eligibility_summary or funding.amount_text or "",
            "confidence": round(confidence, 2),
        },
        {
            "kind": "idea_summary",
            "entity_type": "idea",
            "entity_id": idea.id,
            "title": idea.title,
            "excerpt": idea.short_description or idea.public_summary or "",
            "confidence": round(confidence, 2),
        },
    ]
    return CandidateScore(
        funding=funding,
        idea=idea,
        score_total=round(min(score_total, 1.0), 3),
        confidence=round(confidence, 3),
        topic_fit=round(topic_fit, 3),
        method_fit=round(method_fit, 3),
        funding_fit=round(funding_fit, 3),
        evidence_strength=round(evidence_strength, 3),
        recency=round(recency, 3),
        strategic_value=round(strategic_value, 3),
        effort_reasonableness=round(effort_reasonableness, 3),
        features=features,
        evidence=evidence,
    )


def _generate_entity_to_idea_matches(
    entity_type: str, entity_id: int, entity_terms: set[str], candidate_limit: int, min_score: float
) -> MatchRun:
    run = MatchRun(
        run_type=f"{entity_type}_to_idea",
        source_type=entity_type,
        source_id=entity_id,
        status="running",
        pipeline_version=PIPELINE_VERSION,
        params_json={"candidate_limit": candidate_limit, "min_score": min_score},
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(run)
    db.session.flush()
    ideas = Idea.query.filter(Idea.status != "archived").filter(Idea.status != "hidden").limit(candidate_limit).all()
    scored = []
    for idea in ideas:
        idea_terms = _norm_set((idea.tags_json or []) + (idea.aliases_json or []) + (idea.hub_capabilities_json or []))
        idea_terms |= _keywords(" ".join([idea.title or "", idea.short_description or "", idea.public_summary or ""]))
        shared = sorted(entity_terms & idea_terms)
        score = min(1.0, 0.20 * len(shared))
        if score >= min_score:
            edge = MatchEdge.query.filter_by(
                source_type=entity_type,
                source_id=entity_id,
                target_type="idea",
                target_id=idea.id,
                match_type=f"{entity_type}_to_idea",
            ).first()
            if edge is None:
                edge = MatchEdge(source_type=entity_type, source_id=entity_id, target_type="idea", target_id=idea.id, match_type=f"{entity_type}_to_idea")
            edge.match_run_id = run.id
            edge.score_total = round(score, 3)
            edge.confidence = min(0.9, 0.35 + 0.08 * len(shared))
            edge.score_topic_fit = edge.score_total
            edge.score_evidence_strength = min(1.0, 0.25 + 0.10 * len(shared))
            edge.rationale = f"Entity and Idea share terms: {', '.join(shared[:6])}."
            edge.private_rationale = edge.rationale
            edge.features_json = {"shared_terms": shared, "entity_type": entity_type}
            edge.status = "needs_review" if edge.status in {None, "candidate", "scored", "needs_review"} else edge.status
            db.session.add(edge)
            scored.append(edge)
    run.status = "ok"
    run.candidates_count = len(ideas)
    run.scored_count = len(scored)
    run.finished_at = datetime.now(timezone.utc)
    db.session.commit()
    return run


def _generate_funding_to_entity_via_ideas(funding, entity_type: str, entities: list, min_score: float) -> MatchRun:
    run = MatchRun(
        run_type=f"funding_to_{entity_type}",
        source_type="funding",
        source_id=funding.id,
        status="running",
        pipeline_version=PIPELINE_VERSION,
        params_json={"min_score": min_score},
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(run)
    db.session.flush()
    scored = []
    funding_idea_edges = MatchEdge.query.filter_by(
        source_type="funding", source_id=funding.id, target_type="idea", match_type="funding_to_idea", status="accepted"
    ).all()
    idea_ids = {edge.target_id for edge in funding_idea_edges}
    for entity in entities:
        bridge_edges = MatchEdge.query.filter(
            MatchEdge.source_type == entity_type,
            MatchEdge.source_id == entity.id,
            MatchEdge.target_type == "idea",
            MatchEdge.target_id.in_(idea_ids),
        ).all()
        if not bridge_edges:
            continue
        score = min(1.0, max((edge.score_total or 0.4) for edge in bridge_edges) * 0.9)
        if score < min_score:
            continue
        edge = MatchEdge.query.filter_by(
            source_type="funding",
            source_id=funding.id,
            target_type=entity_type,
            target_id=entity.id,
            match_type=f"funding_to_{entity_type}",
        ).first()
        if edge is None:
            edge = MatchEdge(source_type="funding", source_id=funding.id, target_type=entity_type, target_id=entity.id, match_type=f"funding_to_{entity_type}")
        edge.match_run_id = run.id
        edge.score_total = round(score, 3)
        edge.confidence = 0.6
        edge.score_funding_fit = round(score, 3)
        edge.score_evidence_strength = 0.55
        edge.rationale = f"Funding connects to this {entity_type} through accepted Idea matches."
        edge.private_rationale = edge.rationale
        edge.features_json = {"bridge_idea_ids": sorted(idea_ids), "bridge_edge_ids": [e.id for e in bridge_edges]}
        edge.status = "needs_review" if edge.status in {None, "candidate", "scored", "needs_review"} else edge.status
        db.session.add(edge)
        scored.append(edge)
    run.status = "ok"
    run.candidates_count = len(entities)
    run.scored_count = len(scored)
    run.finished_at = datetime.now(timezone.utc)
    db.session.commit()
    return run


def _entity_terms_for_person(person: Person) -> set[str]:
    terms = _keywords((person.display_name or "") + " " + (person.notes or ""))
    persona = getattr(person, "persona", None)
    if persona:
        terms |= _norm_set((persona.research_focus or []) + (persona.methods or []) + (persona.keywords or []))
    return terms


def upsert_funding_to_idea_edge(candidate: CandidateScore, run: MatchRun) -> tuple[MatchEdge, bool]:
    edge = MatchEdge.query.filter_by(
        source_type="funding",
        source_id=candidate.funding.id,
        target_type="idea",
        target_id=candidate.idea.id,
        match_type="funding_to_idea",
    ).first()
    is_new = edge is None
    if edge is None:
        edge = MatchEdge(
            source_type="funding",
            source_id=candidate.funding.id,
            target_type="idea",
            target_id=candidate.idea.id,
            match_type="funding_to_idea",
        )
    edge.match_run_id = run.id
    edge.score_total = candidate.score_total
    edge.confidence = candidate.confidence
    edge.score_topic_fit = candidate.topic_fit
    edge.score_method_fit = candidate.method_fit
    edge.score_funding_fit = candidate.funding_fit
    edge.score_evidence_strength = candidate.evidence_strength
    edge.score_recency = candidate.recency
    edge.score_strategic_value = candidate.strategic_value
    edge.score_effort_reasonableness = candidate.effort_reasonableness
    edge.rationale = candidate.rationale
    edge.public_rationale = "This funding opportunity may be relevant to this public Idea."
    edge.private_rationale = candidate.rationale
    edge.evidence_json = candidate.evidence
    edge.features_json = candidate.features
    edge.pipeline_version = PIPELINE_VERSION
    edge.input_fingerprint = _edge_fingerprint(candidate)
    if edge.status in {None, "candidate", "scored", "needs_review", "stale"}:
        edge.status = "needs_review"
    edge.visibility = edge.visibility or "private"
    return edge, is_new


def create_hypothesis_from_match(edge: MatchEdge) -> CollaborationHypothesis:
    if edge.match_type != "funding_to_idea":
        raise ValueError("Only funding_to_idea matches can create hypotheses in Phase 4.")
    funding = db.session.get(FundingOpportunity, edge.source_id)
    idea = db.session.get(Idea, edge.target_id)
    if funding is None or idea is None:
        raise ValueError("Match edge no longer points to an existing funding opportunity and idea.")
    hypothesis = CollaborationHypothesis(
        title=f"{idea.title} + {funding.title}",
        target_type="idea",
        target_id=idea.id,
        idea_id=idea.id,
        funding_opportunity_id=funding.id,
        primary_match_edge_id=edge.id,
        related_match_edge_ids_json=[edge.id],
        status="needs_review",
        priority="normal" if (edge.score_total or 0) < 0.75 else "high",
        hypothesis_summary=(
            f"{funding.title} may support work around {idea.title}. "
            "This is a private draft hypothesis for Hub review."
        ),
        evidence_summary=edge.rationale,
        funding_fit_summary=f"Funding match score: {edge.score_total or 0:.2f}.",
        effort_summary=f"Funding effort: {funding.effort_index or 'unknown'}.",
        recommended_action="Review the funding and idea fit before using this for outreach or public display.",
        score_fit=edge.score_total,
        score_funding=edge.score_funding_fit,
        score_effort=edge.score_effort_reasonableness,
        score_relationship=edge.score_evidence_strength,
        score_strategic=edge.score_strategic_value,
        score_total=edge.score_total,
        score_breakdown_json=edge.features_json or {},
        evidence_json=edge.evidence_json or [],
        pipeline_version=PIPELINE_VERSION,
        input_fingerprint=edge.input_fingerprint,
    )
    db.session.add(hypothesis)
    db.session.commit()
    return hypothesis


def create_hypothesis_for_target(target_type: str, target_id: int) -> CollaborationHypothesis:
    edges = (
        MatchEdge.query.filter(MatchEdge.status == "accepted")
        .filter(
            ((MatchEdge.source_type == target_type) & (MatchEdge.source_id == target_id))
            | ((MatchEdge.target_type == target_type) & (MatchEdge.target_id == target_id))
        )
        .order_by(MatchEdge.score_total.desc().nullslast(), MatchEdge.updated_at.desc())
        .limit(10)
        .all()
    )
    if not edges:
        raise ValueError("No accepted matches are available for this target.")
    best = edges[0]
    title = f"Collaboration hypothesis for {target_type} #{target_id}"
    idea_id = None
    funding_id = None
    for edge in edges:
        if edge.source_type == "idea":
            idea_id = edge.source_id
        if edge.target_type == "idea":
            idea_id = edge.target_id
        if edge.source_type == "funding":
            funding_id = edge.source_id
        if edge.target_type == "funding":
            funding_id = edge.target_id
    score_total = max(edge.score_total or 0 for edge in edges)
    hypothesis = CollaborationHypothesis(
        title=title,
        target_type=target_type,
        target_id=target_id,
        idea_id=idea_id,
        funding_opportunity_id=funding_id,
        primary_match_edge_id=best.id,
        related_match_edge_ids_json=[edge.id for edge in edges],
        status="needs_review",
        priority="high" if score_total >= 0.75 else "normal",
        hypothesis_summary=f"{target_type.title()} #{target_id} has {len(edges)} accepted relationship(s) that may support a Hub collaboration hypothesis.",
        evidence_summary="; ".join((edge.rationale or "") for edge in edges[:3] if edge.rationale),
        recommended_action="Review the accepted matches and refine this hypothesis before outreach or public use.",
        score_total=score_total,
        score_fit=score_total,
        score_relationship=max(edge.score_evidence_strength or 0 for edge in edges),
        score_breakdown_json={"accepted_match_edge_ids": [edge.id for edge in edges]},
        evidence_json=[item for edge in edges for item in (edge.evidence_json or [])],
        pipeline_version=PIPELINE_VERSION,
    )
    db.session.add(hypothesis)
    db.session.commit()
    return hypothesis


def _edge_fingerprint(candidate: CandidateScore) -> str:
    raw = "|".join(
        [
            str(candidate.funding.id),
            candidate.funding.title or "",
            str(candidate.idea.id),
            candidate.idea.title or "",
            ",".join(candidate.features.get("shared_terms") or []),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _norm_set(values: list[str]) -> set[str]:
    return {_norm(value) for value in values if _norm(value)}


def _norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _keywords(text: str) -> set[str]:
    stop = {
        "and",
        "the",
        "for",
        "with",
        "from",
        "this",
        "that",
        "into",
        "over",
        "under",
        "award",
        "funding",
        "opportunity",
        "research",
        "project",
    }
    return {word for word in re.findall(r"[a-z0-9][a-z0-9-]{2,}", text.lower()) if word not in stop}
