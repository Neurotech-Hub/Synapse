"""Persona rebuild mode selection (full vs incremental vs light)."""

from __future__ import annotations

import os
from typing import Literal

PersonaRebuildMode = Literal["full", "incremental", "light_refresh"]


def _parse_mode(raw: str, default: PersonaRebuildMode) -> PersonaRebuildMode:
    s = (raw or "").strip().lower()
    if s in ("full", "incremental", "light_refresh"):
        return s  # type: ignore[return-value]
    return default


def poll_persona_rebuild_mode() -> PersonaRebuildMode:
    """Mode used after ingest poll burst (default: incremental)."""

    return _parse_mode(os.environ.get("SYNAPSE_POLL_PERSONA_REBUILD_MODE") or "", "incremental")


def dashboard_stale_rebuild_mode() -> PersonaRebuildMode:
    """Mode for dashboard “refresh stale ready identities” batch."""

    return _parse_mode(
        os.environ.get("SYNAPSE_DASH_IDENTITY_REBUILD_MODE") or os.environ.get("SYNAPSE_DASHBOARD_IDENTITY_REBUILD_MODE") or "",
        "incremental",
    )


def default_manual_rebuild_mode() -> PersonaRebuildMode:
    """Default for explicit admin “rebuild persona” when not overridden."""

    return _parse_mode(os.environ.get("SYNAPSE_MANUAL_PERSONA_REBUILD_MODE") or "", "full")
