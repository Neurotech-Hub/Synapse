"""In-memory poll run tracking for responsive admin UX (dashboard progress)."""

from __future__ import annotations

import copy
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from flask import Flask

_POLL_LOCK = threading.Lock()
_POLLS: dict[str, dict[str, Any]] = {}
_ACTIVE_POLL_RUN_ID: str | None = None


def snapshot_poll(run_id: str) -> dict[str, Any] | None:
    with _POLL_LOCK:
        st = _POLLS.get(run_id)
        return copy.deepcopy(st) if st is not None else None


def is_poll_running() -> bool:
    """True only while an in-flight poll owns ``_ACTIVE_POLL_RUN_ID``.

    Self-healing: clears stale globals if the tracked run finished or lost its state dict
    (e.g. thread died without ``finally``, dev reload edge cases).
    """

    global _ACTIVE_POLL_RUN_ID

    with _POLL_LOCK:
        rid = _ACTIVE_POLL_RUN_ID
        if rid is None:
            return False
        st = _POLLS.get(rid)
        if st is None:
            _ACTIVE_POLL_RUN_ID = None
            return False
        if bool(st.get("finished")):
            _ACTIVE_POLL_RUN_ID = None
            return False
        return True


def start_background_poll(app: Flask) -> tuple[str | None, str]:
    """Start a threaded poll run. Returns (run_id, err) where err is '' or 'busy' / 'no_sources'."""
    global _ACTIVE_POLL_RUN_ID

    from app.models import Source

    with app.app_context():
        sources = Source.query.filter_by(enabled=True, pending=False).order_by(Source.id).all()
        if not sources:
            return None, "no_sources"
        snapshots = [
            {
                "id": s.id,
                "url": s.url,
                "kind": s.kind,
            }
            for s in sources
        ]

    run_id = str(uuid.uuid4())
    state: dict[str, Any] = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished": False,
        "overall_ok": None,
        "poll_log_id": None,
        "error": None,
        "sources": [
            {**snap, "state": "pending", "message": ""} for snap in snapshots
        ],
    }

    with _POLL_LOCK:
        if _ACTIVE_POLL_RUN_ID is not None:
            return None, "busy"
        _POLLS[run_id] = state
        _ACTIVE_POLL_RUN_ID = run_id

    # Accept either a Flask app or a LocalProxy (e.g. current_app); only proxies have _get_current_object.
    unwrap = getattr(app, "_get_current_object", None)
    app_ref = unwrap() if callable(unwrap) else app

    def worker() -> None:
        """Always release ``_ACTIVE_POLL_RUN_ID`` for this ``run_id`` on thread exit."""

        def release_active() -> None:
            global _ACTIVE_POLL_RUN_ID

            with _POLL_LOCK:
                if _ACTIVE_POLL_RUN_ID == run_id:
                    _ACTIVE_POLL_RUN_ID = None

        try:
            from app.ingest.pipeline import run_poll

            def on_source_step(**kw: Any) -> None:
                phase = kw["phase"]
                src = kw["source"]
                with _POLL_LOCK:
                    bucket = _POLLS.get(run_id)
                    if not bucket:
                        return
                    rows = bucket["sources"]
                    if phase == "running":
                        for r in rows:
                            if r["id"] == src.id:
                                r["state"] = "running"
                                break
                    elif phase == "done":
                        ok_one = kw["ok"]
                        msg = kw["message"]
                        for r in rows:
                            if r["id"] == src.id:
                                r["state"] = "ok" if ok_one else "error"
                                r["message"] = msg[:500]
                                break

            try:
                with app_ref.app_context():
                    log = run_poll(on_source_step=on_source_step)
                    with _POLL_LOCK:
                        bucket = _POLLS.get(run_id)
                        if bucket:
                            bucket["finished"] = True
                            bucket["overall_ok"] = bool(log.ok)
                            bucket["poll_log_id"] = log.id
            except Exception as e:  # noqa: BLE001
                with _POLL_LOCK:
                    bucket = _POLLS.get(run_id)
                    if bucket:
                        bucket["finished"] = True
                        bucket["overall_ok"] = False
                        bucket["error"] = str(e)
        finally:
            release_active()

    try:
        threading.Thread(target=worker, daemon=True).start()
    except RuntimeError:
        # e.g. cannot start thread — roll back advertised "busy" state.
        with _POLL_LOCK:
            _POLLS.pop(run_id, None)
            if _ACTIVE_POLL_RUN_ID == run_id:
                _ACTIVE_POLL_RUN_ID = None
        return None, "thread_start_failed"
    return run_id, ""
