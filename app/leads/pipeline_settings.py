"""Admin-persisted Hub lead singleton (``id=1``): default corpus organization."""

from __future__ import annotations

from app.extensions import db
from app.models import LeadPipelineSettings


def get_singleton() -> LeadPipelineSettings:
    """Return the settings row, creating the singleton if missing."""

    row = db.session.get(LeadPipelineSettings, 1)
    if row is None:
        row = LeadPipelineSettings(id=1, hub_organization_id=None)
        db.session.add(row)
        db.session.commit()
    return row
