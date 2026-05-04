"""Reconcile ``LeadReport`` rows left ``running`` after process death (e.g. dev server reload)."""

from __future__ import annotations

from datetime import datetime, timezone

_INTERRUPT_MSG = (
    "Interrupted: the application restarted or crashed while this report was running."
)


def reconcile_interrupted_lead_reports() -> int:
    """Mark any ``running`` reports as ``failed`` with ``completed_at`` set.

    In-memory ``report_progress`` state resets on restart; DB rows can still say
    ``running``. Call once at app startup (and safe to call manually).

    Returns the number of rows updated.
    """
    from sqlalchemy.exc import OperationalError

    from app.extensions import db
    from app.models import LeadReport

    try:
        rows = LeadReport.query.filter_by(status="running").all()
    except OperationalError:
        db.session.rollback()
        return 0
    if not rows:
        return 0
    now = datetime.now(timezone.utc)
    for r in rows:
        r.status = "failed"
        r.completed_at = now
        prev = (r.error_detail or "").strip()
        r.error_detail = f"{prev}\n\n{_INTERRUPT_MSG}" if prev else _INTERRUPT_MSG
    db.session.commit()
    return len(rows)
