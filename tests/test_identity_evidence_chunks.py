"""Persona evidence packing (tiered excerpts + budgets)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.identity import evidence


@dataclass
class _FakeSrc:
    kind: str = "rss_feed"


@dataclass
class _FakeItem:
    id: int
    title: str
    snippet: str
    link: str
    published_at: datetime
    source: _FakeSrc = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.source is None:
            self.source = _FakeSrc()


def test_chunks_for_prompt_uses_shorter_bodies_after_full_text_tier(monkeypatch) -> None:
    monkeypatch.setenv("SYNAPSE_IDENTITY_FULL_TEXT_ITEMS", "3")
    monkeypatch.setenv("SYNAPSE_IDENTITY_CONTENT_BUDGET_CHARS", "28000")

    dense = "word " * 4500  # huge snippet
    items = [
        _FakeItem(i, f"Title-{i}", dense, f"https://ex/{i}", datetime.now(timezone.utc)) for i in range(12)
    ]
    out = evidence.chunks_for_prompt(items)  # type: ignore[arg-type]
    parts = out.split("\n\n---\n\n")
    assert len(parts) >= 4
    assert len(parts[0]) > len(parts[-1])
