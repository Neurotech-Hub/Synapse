"""In-memory progress for background public Latest curation (multi-batch until queue drained)."""

from __future__ import annotations

import copy
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from flask import Flask

_FEED_LOCK = threading.Lock()
_FEED_RUNS: dict[str, dict[str, Any]] = {}
_ACTIVE_FEED_RUN_ID: str | None = None

# Hard cap so a pathological queue cannot loop forever in one worker.
_MAX_BATCH_ITERATIONS = 500


def snapshot_public_feed_curation(run_id: str) -> dict[str, Any] | None:
    with _FEED_LOCK:
        st = _FEED_RUNS.get(run_id)
        return copy.deepcopy(st) if st is not None else None


def public_feed_curation_active_run_id() -> str | None:
    """Run id for the in-flight job, if any (for resuming progress UI after refresh)."""

    global _ACTIVE_FEED_RUN_ID

    with _FEED_LOCK:
        rid = _ACTIVE_FEED_RUN_ID
        if rid is None:
            return None
        st = _FEED_RUNS.get(rid)
        if st is None or bool(st.get("finished")):
            _ACTIVE_FEED_RUN_ID = None
            return None
        return rid


def is_public_feed_curation_running() -> bool:
    """True while a background curation worker owns the active run id."""

    return public_feed_curation_active_run_id() is not None


def _release_active(run_id: str) -> None:
    global _ACTIVE_FEED_RUN_ID

    with _FEED_LOCK:
        if _ACTIVE_FEED_RUN_ID == run_id:
            _ACTIVE_FEED_RUN_ID = None


def _patch_state(run_id: str, **kw: Any) -> None:
    with _FEED_LOCK:
        bucket = _FEED_RUNS.get(run_id)
        if not bucket:
            return
        for k, v in kw.items():
            bucket[k] = v


def start_background_public_feed_curation(app: Flask) -> tuple[str | None, str]:
    """Drain the uncurated queue in repeated batches (48 rows per Ollama call)."""

    global _ACTIVE_FEED_RUN_ID

    from app.public_feed.curate import count_uncurated_public_feed_candidates, run_public_feed_curation_batch

    run_id = str(uuid.uuid4())
    state: dict[str, Any] = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished": False,
        "message": "Starting…",
        "batches_completed": 0,
        "total_processed": 0,
        "total_shown": 0,
        "total_hidden": 0,
        "uncurated_remaining": None,
        "error": None,
        "warning": None,
        "stopped_reason": None,
    }

    with _FEED_LOCK:
        if _ACTIVE_FEED_RUN_ID is not None:
            return None, "busy"
        _FEED_RUNS[run_id] = state
        _ACTIVE_FEED_RUN_ID = run_id

    unwrap = getattr(app, "_get_current_object", None)
    app_ref = unwrap() if callable(unwrap) else app

    def worker() -> None:
        batches_completed = 0
        total_processed = 0
        total_shown = 0
        total_hidden = 0
        warning: str | None = None
        fatal: str | None = None
        stopped_reason = "complete"

        try:
            with app_ref.app_context():
                while batches_completed < _MAX_BATCH_ITERATIONS:
                    remaining = int(count_uncurated_public_feed_candidates())
                    _patch_state(
                        run_id,
                        uncurated_remaining=remaining,
                        message=f"Queue: {remaining} uncurated — preparing next batch…",
                    )
                    if remaining == 0:
                        stopped_reason = "empty"
                        break

                    _patch_state(
                        run_id,
                        message=f"Calling Ollama (up to 48 items; {remaining} uncurated in queue)…",
                    )
                    out = run_public_feed_curation_batch(limit=48, commit=True)
                    status = out.get("status")

                    if status == "empty":
                        stopped_reason = "empty_mid"
                        break

                    if status == "failed":
                        fatal = out.get("detail") or "Batch failed."
                        stopped_reason = "error"
                        break

                    if status != "ok":
                        fatal = f"Unexpected batch status: {status!r}"
                        stopped_reason = "error"
                        break

                    proc = int(out.get("processed") or 0)
                    batches_completed += 1
                    total_processed += proc
                    total_shown += int(out.get("shown") or 0)
                    total_hidden += int(out.get("hidden") or 0)
                    remaining_after = int(count_uncurated_public_feed_candidates())

                    _patch_state(
                        run_id,
                        batches_completed=batches_completed,
                        total_processed=total_processed,
                        total_shown=total_shown,
                        total_hidden=total_hidden,
                        uncurated_remaining=remaining_after,
                        message=(
                            f"Batch {batches_completed} saved: {proc} row(s) "
                            f"({out.get('shown', 0)} shown, {out.get('hidden', 0)} hidden). "
                            f"About {remaining_after} still uncurated."
                        ),
                    )

                    if proc == 0:
                        warning = (
                            "The last batch updated 0 rows while the queue was non-empty — stopping to avoid a loop."
                        )
                        stopped_reason = "stall"
                        break

                    if remaining_after >= remaining:
                        warning = "Queue size did not shrink after a batch — stopping to avoid a loop."
                        stopped_reason = "stall"
                        break

                    if remaining_after == 0:
                        stopped_reason = "complete"
                        break
                else:
                    warning = f"Stopped after {_MAX_BATCH_ITERATIONS} batches (safety cap); run again if needed."
                    stopped_reason = "cap"

        except Exception as e:  # noqa: BLE001
            fatal = str(e)
            stopped_reason = "error"
        finally:
            try:
                with app_ref.app_context():
                    final_rem: int | None = int(count_uncurated_public_feed_candidates())
            except Exception:  # noqa: BLE001
                final_rem = None

            if fatal:
                end_msg = f"Stopped with error: {fatal}"
            elif warning:
                end_msg = f"Stopped — {warning}"
            else:
                rem_bit = (
                    f"{final_rem} still uncurated — run again later if you want to drain further."
                    if (final_rem or 0) > 0
                    else "Uncurated queue is clear."
                )
                end_msg = (
                    f"Finished: {batches_completed} batch(es), {total_processed} row(s) updated "
                    f"({total_shown} shown, {total_hidden} hidden). {rem_bit}"
                )

            _patch_state(
                run_id,
                finished=True,
                batches_completed=batches_completed,
                total_processed=total_processed,
                total_shown=total_shown,
                total_hidden=total_hidden,
                uncurated_remaining=final_rem,
                message=end_msg,
                error=fatal,
                warning=warning,
                stopped_reason=stopped_reason,
            )
            _release_active(run_id)

    try:
        threading.Thread(target=worker, daemon=True).start()
    except RuntimeError:
        with _FEED_LOCK:
            _FEED_RUNS.pop(run_id, None)
            if _ACTIVE_FEED_RUN_ID == run_id:
                _ACTIVE_FEED_RUN_ID = None
        return None, "thread_start_failed"
    return run_id, ""
