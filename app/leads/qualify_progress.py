"""Background execution for lead qualification (single-flight guard)."""

from __future__ import annotations

import json
import threading
import traceback
from typing import Any

from flask import Flask

_QUAL_LOCK = threading.Lock()
_QUAL_BUSY = False
_LAST_DETAIL: dict[str, Any] = {}


def is_lead_qual_running() -> bool:
    with _QUAL_LOCK:
        return bool(_QUAL_BUSY)


def last_lead_qual_result() -> dict[str, Any]:
    with _QUAL_LOCK:
        return dict(_LAST_DETAIL)


def start_background_lead_qualify(app: Flask) -> tuple[bool, str]:
    """Starts a daemon worker. Returns ``(started, err)`` — err ``busy`` if already running."""

    global _QUAL_BUSY

    unwrap = getattr(app, "_get_current_object", None)
    app_ref = unwrap() if callable(unwrap) else app

    with _QUAL_LOCK:
        if _QUAL_BUSY:
            return False, "busy"
        _QUAL_BUSY = True

    def worker() -> None:
        global _QUAL_BUSY, _LAST_DETAIL

        from app.extensions import db
        from app.leads.qualification import run_lead_qualification
        from app.models import PollLog

        ok = False
        detail_txt = ""
        try:
            with app_ref.app_context():
                counts = run_lead_qualification()
                detail_txt = json.dumps(counts, sort_keys=True)
                log = PollLog(ok=True, detail=f"[lead-qual] {detail_txt}")
                db.session.add(log)
                db.session.commit()
                ok = True
                _LAST_DETAIL = {"ok": True, **counts}
        except Exception as e:  # noqa: BLE001
            ok = False
            tb_tail = traceback.format_exc()[-2000:]
            detail_txt = f"ERROR {e}\n{tb_tail}"
            _LAST_DETAIL = {"ok": False, "error": str(e)}
            try:
                with app_ref.app_context():
                    db.session.rollback()
                    log = PollLog(ok=False, detail=f"[lead-qual] {detail_txt}")
                    db.session.add(log)
                    db.session.commit()
            except Exception:  # noqa: BLE001
                pass
        finally:
            with _QUAL_LOCK:
                _QUAL_BUSY = False

    threading.Thread(target=worker, daemon=True).start()
    return True, ""
