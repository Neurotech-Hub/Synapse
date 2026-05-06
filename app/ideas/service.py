from __future__ import annotations

import re

from app.models import Idea

IDEA_TYPES = (
    "research_theme",
    "technical_capability",
    "buildable_concept",
    "method_cluster",
    "funding_theme",
    "strategic_area",
    "public_resource_topic",
    "unknown",
)

IDEA_STATUSES = ("draft", "review", "public", "private", "archived", "hidden", "merged")
IDEA_CREATED_VIA = ("manual", "persona_extract", "content_extract", "funding_extract", "admin_seed", "imported")


def parse_semicolon_list(raw: str | None) -> list[str]:
    values: list[str] = []
    for part in (raw or "").split(";"):
        item = " ".join(part.strip().split())
        if item and item not in values:
            values.append(item)
    return values


def allocate_idea_slug(title: str, *, exclude_id: int | None = None) -> str:
    base = _slug_base(title) or "idea"
    base = base[:260].strip("-_") or "idea"
    candidate = base
    suffix = 2
    while True:
        query = Idea.query.filter_by(slug=candidate)
        if exclude_id is not None:
            query = query.filter(Idea.id != exclude_id)
        if query.first() is None:
            return candidate
        extra = f"_{suffix}"
        candidate = f"{base[: 260 - len(extra)]}{extra}"
        suffix += 1


def idea_is_publicly_visible(idea: Idea) -> bool:
    return bool(idea.is_public and idea.is_reviewed and idea.status == "public" and idea.archived_at is None)


def _slug_base(raw: str | None) -> str:
    if raw is None:
        return ""
    slug = str(raw).strip().lower().replace(" ", "_")
    slug = re.sub(r"[^a-z0-9_-]+", "", slug)
    slug = re.sub(r"_+", "_", slug)
    return slug.strip("_-")
