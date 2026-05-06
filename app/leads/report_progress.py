"""Background execution for Hub-centric lead reports (single-flight guard)."""

from __future__ import annotations

import json
import threading
import traceback
from typing import Any

from flask import Flask

_REPORT_LOCK = threading.Lock()
_REPORT_BUSY = False
_ACTIVE_REPORT_ID: int | None = None
_LAST_DETAIL: dict[str, Any] = {}
_ACTIVE_PHASE: str = ""


def is_lead_report_running() -> bool:
    with _REPORT_LOCK:
        return bool(_REPORT_BUSY)


def active_report_id() -> int | None:
    with _REPORT_LOCK:
        return _ACTIVE_REPORT_ID


def active_report_phase() -> str:
    """Short human-readable step while a report job holds the runner lock."""

    with _REPORT_LOCK:
        return _ACTIVE_PHASE


def set_lead_report_phase(phase: str) -> None:
    """Set current step hint (called from worker / pipeline). Cleared when idle."""

    global _ACTIVE_PHASE

    with _REPORT_LOCK:
        _ACTIVE_PHASE = (phase or "").strip()


def last_lead_report_result() -> dict[str, Any]:
    with _REPORT_LOCK:
        return dict(_LAST_DETAIL)


def start_background_lead_report(app: Flask, report_id: int) -> tuple[bool, str]:
    """Starts daemon worker for one ``LeadReport`` row. ``(started, err)`` — err ``busy`` if gated."""

    global _REPORT_BUSY, _ACTIVE_REPORT_ID

    unwrap = getattr(app, "_get_current_object", None)
    app_ref = unwrap() if callable(unwrap) else app
    rid = int(report_id)

    with _REPORT_LOCK:
        if _REPORT_BUSY:
            return False, "busy"
        _REPORT_BUSY = True
        _ACTIVE_REPORT_ID = rid

    def worker() -> None:
        global _REPORT_BUSY, _LAST_DETAIL, _ACTIVE_REPORT_ID, _ACTIVE_PHASE

        from app.extensions import db
        from app.leads.report_pipeline import run_lead_report_job
        from app.models import LeadReport, PollLog

        ok = False
        detail_txt = ""
        status_after = ""
        try:
            set_lead_report_phase("Starting…")
            with app_ref.app_context():
                run_lead_report_job(rid)
                row = db.session.get(LeadReport, rid)
                ok = row is not None and row.status == "ok"
                status_after = (row.status or "") if row else "missing"
                detail_txt = json.dumps(
                    {
                        "report_id": rid,
                        "status": status_after,
                        "fingerprint": (row.input_fingerprint if row else None),
                        "completed_at": (row.completed_at.isoformat() if row and row.completed_at else None),
                    },
                    default=str,
                )
                slog = PollLog(ok=ok, detail=f"[lead-candidate] {detail_txt}")
                db.session.add(slog)
                db.session.commit()
                _LAST_DETAIL = {"ok": ok, "report_id": rid, "status": status_after}
        except Exception as e:  # noqa: BLE001
            ok = False
            tb_tail = traceback.format_exc()[-2000:]
            detail_txt = f"ERROR {e}\n{tb_tail}"
            _LAST_DETAIL = {"ok": False, "report_id": rid, "error": str(e)}
            try:
                with app_ref.app_context():
                    db.session.rollback()
                    slog = PollLog(ok=False, detail=f"[lead-candidate] {detail_txt}")
                    db.session.add(slog)
                    db.session.commit()
            except Exception:  # noqa: BLE001
                pass
        finally:
            with _REPORT_LOCK:
                _REPORT_BUSY = False
                _ACTIVE_REPORT_ID = None
                _ACTIVE_PHASE = ""

    threading.Thread(target=worker, daemon=True).start()
    return True, ""
