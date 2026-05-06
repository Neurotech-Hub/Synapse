from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.extensions import db
from app.ideas.service import allocate_idea_slug
from app.llm.execute import LLMExecutionResult, execute_prompt
from app.models import ContentItem, Idea, IdeaSuggestion, PersonaSnapshot


def generate_idea_suggestions_from_persona(
    snapshot: PersonaSnapshot,
    *,
    provider: str | None = None,
    allow_openai: bool = False,
    mock_provider=None,
) -> LLMExecutionResult:
    entity_type, entity_name = _snapshot_subject(snapshot)
    variables = {
        "entity_type": entity_type,
        "entity_name": entity_name,
        "persona_snapshot": {
            "research_focus": snapshot.research_focus or [],
            "methods": snapshot.methods or [],
            "keywords": snapshot.keywords or [],
            "current_projects": snapshot.current_projects or [],
            "funding_signals": snapshot.funding_signals or [],
            "notes": snapshot.notes or "",
        },
        "recent_evidence_summary": "",
        "schema": {"schema_version": "1.0", "candidate_ideas": [], "confidence": 0.0},
    }
    result = execute_prompt(
        "idea_extract_from_persona",
        variables,
        provider=provider,
        source_type="persona_snapshot",
        source_id=snapshot.id,
        allow_openai=allow_openai,
        mock_provider=mock_provider,
    )
    if result.ok and result.data:
        for item in result.data.get("candidate_ideas") or []:
            _create_suggestion(
                item,
                source_type="persona_snapshot",
                source_id=snapshot.id,
                llm_run_id=result.run.id if result.run else None,
            )
        db.session.commit()
    return result


def generate_idea_suggestions_from_content(
    content_item: ContentItem,
    *,
    provider: str | None = None,
    allow_openai: bool = False,
    mock_provider=None,
) -> LLMExecutionResult:
    evidence = pack_content_item_evidence(content_item)
    variables = {
        "content_item_evidence": evidence,
        "existing_context": {"existing_idea_titles": [row.title for row in Idea.query.order_by(Idea.title.asc()).limit(200)]},
        "schema": {"schema_version": "1.0", "candidate_ideas": [], "confidence": 0.0},
    }
    result = execute_prompt(
        "idea_extract_from_content_item",
        variables,
        provider=provider,
        source_type="content_item",
        source_id=content_item.id,
        allow_openai=allow_openai,
        mock_provider=mock_provider,
    )
    if result.ok and result.data:
        for item in result.data.get("candidate_ideas") or []:
            _create_suggestion(
                item,
                source_type="content_item",
                source_id=content_item.id,
                llm_run_id=result.run.id if result.run else None,
            )
        db.session.commit()
    return result


def generate_idea_suggestions_from_content_item(content_item_id: int, **kwargs) -> LLMExecutionResult:
    item = db.session.get(ContentItem, content_item_id)
    if item is None:
        raise ValueError(f"ContentItem {content_item_id} not found.")
    return generate_idea_suggestions_from_content(item, **kwargs)


def pack_content_item_evidence(content_item: ContentItem, *, max_chars: int = 8000) -> dict[str, Any]:
    source = content_item.source
    snippet = (content_item.snippet or "")[:max_chars]
    return {
        "content_item_id": content_item.id,
        "title": content_item.title or "",
        "url": content_item.link or "",
        "source_url": source.url if source else "",
        "source_kind": source.kind if source else "",
        "published_at": content_item.published_at.isoformat() if content_item.published_at else None,
        "first_seen_at": content_item.first_seen_at.isoformat() if content_item.first_seen_at else None,
        "snippet": snippet,
    }


def accept_idea_suggestion(suggestion: IdeaSuggestion) -> Idea:
    existing = suggestion.duplicate_candidate
    idea = existing or Idea(
        title=suggestion.title,
        slug=allocate_idea_slug(suggestion.title),
        idea_type=suggestion.idea_type or "unknown",
        created_via="persona_extract" if suggestion.source_type == "persona_snapshot" else "content_extract",
    )
    idea.short_description = suggestion.short_description or idea.short_description
    idea.public_summary = suggestion.public_summary or idea.public_summary
    idea.tags_json = _merge_lists(idea.tags_json or [], suggestion.tags_json or [])
    idea.aliases_json = _merge_lists(idea.aliases_json or [], suggestion.aliases_json or [])
    idea.hub_capabilities_json = _merge_lists(idea.hub_capabilities_json or [], suggestion.hub_capabilities_json or [])
    idea.evidence_refs_json = _merge_lists(idea.evidence_refs_json or [], suggestion.evidence_json or [])
    idea.confidence_score = suggestion.confidence
    db.session.add(idea)
    db.session.flush()
    suggestion.status = "merged" if existing else "accepted"
    suggestion.accepted_idea_id = idea.id
    suggestion.reviewed_at = datetime.now(timezone.utc)
    db.session.commit()
    return idea


def reject_idea_suggestion(suggestion: IdeaSuggestion) -> None:
    suggestion.status = "rejected"
    suggestion.reviewed_at = datetime.now(timezone.utc)
    db.session.commit()


def _create_suggestion(item: dict[str, Any], *, source_type: str, source_id: int, llm_run_id: int | None) -> IdeaSuggestion:
    title = str(item.get("title") or "").strip()
    if not title:
        title = "Untitled idea suggestion"
    duplicate_id, duplicate_reason, duplicate_confidence = find_duplicate_idea(item_title=title, aliases=_as_list(item.get("aliases")), tags=_as_list(item.get("tags")))
    suggestion = IdeaSuggestion(
        source_type=source_type,
        source_id=source_id,
        title=title[:240],
        idea_type=str(item.get("idea_type") or "unknown"),
        short_description=str(item.get("short_description") or "")[:500] or None,
        public_summary=item.get("public_summary_draft") or item.get("public_summary"),
        tags_json=_as_list(item.get("tags")),
        aliases_json=_as_list(item.get("aliases")),
        hub_capabilities_json=_as_list(item.get("hub_capabilities") or item.get("technologies")),
        evidence_json=_as_list(item.get("evidence_refs") or item.get("supporting_points") or item.get("evidence_summary")),
        duplicate_candidate_id=duplicate_id,
        duplicate_reason=duplicate_reason,
        duplicate_confidence=duplicate_confidence,
        confidence=_float_or_none(item.get("confidence") or item.get("confidence_score") or item.get("evidence_strength")),
        llm_run_id=llm_run_id,
    )
    db.session.add(suggestion)
    return suggestion


def find_duplicate_idea(*, item_title: str, aliases: list[str], tags: list[str]) -> tuple[int | None, str | None, float | None]:
    candidates = {_norm(item_title), *(_norm(alias) for alias in aliases)}
    tag_set = {_norm(tag) for tag in tags if _norm(tag)}
    for idea in Idea.query.all():
        existing = {_norm(idea.title), *(_norm(alias) for alias in (idea.aliases_json or []))}
        if candidates & existing:
            return idea.id, "normalized title or alias match", 1.0
        idea_tags = {_norm(tag) for tag in (idea.tags_json or []) if _norm(tag)}
        if tag_set and idea_tags:
            overlap = tag_set & idea_tags
            ratio = len(overlap) / max(len(tag_set), 1)
            if len(overlap) >= 2 or ratio >= 0.6:
                return idea.id, f"tag overlap: {', '.join(sorted(overlap))}", round(min(0.95, 0.5 + ratio / 2), 2)
        slugish = _norm((idea.slug or "").replace("_", " "))
        if slugish and _norm(item_title) and (slugish in _norm(item_title) or _norm(item_title) in slugish):
            return idea.id, "slug/title similarity", 0.75
    return None, None, None


def _norm(raw: str | None) -> str:
    return " ".join(str(raw or "").strip().lower().replace("-", " ").replace("_", " ").split())


def _snapshot_subject(snapshot: PersonaSnapshot) -> tuple[str, str]:
    if snapshot.person is not None:
        return "person", snapshot.person.display_name
    if snapshot.organization is not None:
        return "organization", snapshot.organization.display_name
    if snapshot.building is not None:
        return "place", snapshot.building.display_name
    return "unknown", f"Persona snapshot {snapshot.id}"


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return [x for x in value if x]
    if value:
        return [value]
    return []


def _merge_lists(a: list, b: list) -> list:
    out = list(a)
    for item in b:
        if item and item not in out:
            out.append(item)
    return out


def _float_or_none(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
