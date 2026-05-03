"""Entities attached to sources; catalog material for prompts."""

from __future__ import annotations

from app.models import ContentItem, Entity, Source


def entities_for_union(*, hub_items: list[ContentItem], candidate_source: Source, cap: int) -> list[Entity]:
    """Hub slice sources ∪ candidate source, distinct entities preserving order."""

    ordered: list[Entity] = []
    seen: set[int] = set()

    def add_from_source(src: Source) -> None:
        for ent in getattr(src, "entities", ()) or []:
            if len(ordered) >= cap:
                return
            if ent.id not in seen:
                seen.add(ent.id)
                ordered.append(ent)

    for ci in hub_items:
        if ci.source:
            add_from_source(ci.source)
        if len(ordered) >= cap:
            break
    if len(ordered) < cap:
        add_from_source(candidate_source)
    return ordered[:cap]


def format_entity_catalog_lines(entities: list[Entity]) -> str:
    if not entities:
        return "(no entities tagged — return primary_entity_slug null)."
    lines: list[str] = []
    for e in entities:
        lines.append(f"- slug={e.slug} kind={e.kind} name={e.display_name} id={e.id}")
    return "\n".join(lines)


def entity_id_for_slug(slug: str | None) -> int | None:
    if slug is None:
        return None
    s = str(slug).strip()
    if not s:
        return None
    row = Entity.query.filter_by(slug=s).first()
    return row.id if row else None


def normalize_fingerprint(raw: str | None, max_len: int = 512) -> str | None:
    if raw is None:
        return None
    t = " ".join(str(raw).strip().lower().split())
    if not t:
        return None
    return t[:max_len]
