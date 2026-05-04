"""Jinja helpers for admin datetimes shown in the browser's local timezone."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Final

from markupsafe import Markup, escape

_DT_STYLES: Final[frozenset[str]] = frozenset({"date", "datetime", "datetime_sec"})


def _normalize_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def local_dt_markup(dt: datetime | None, style: str = "datetime") -> Markup:
    """Emit ``<time>`` for client-side ``Intl`` formatting; ``None`` → empty."""
    if dt is None:
        return Markup("")
    if style not in _DT_STYLES:
        style = "datetime"
    aware = _normalize_utc(dt)
    iso = aware.isoformat()
    s_esc = escape(style)
    i_esc = escape(iso)
    return Markup(
        f'<time class="syn-local-dt" datetime="{i_esc}" data-dt-style="{s_esc}"></time>'
    )
