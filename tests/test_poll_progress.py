"""Poll progress module: busy flag hygiene."""

import pytest

import app.ingest.poll_progress as poll_progress


def test_is_poll_running_false_when_finished_stale_pointer():
    """Finished runs should not keep the Poll button blocked."""
    rid = "test-run-heal"

    with poll_progress._POLL_LOCK:
        poll_progress._POLLS.clear()
        poll_progress._ACTIVE_POLL_RUN_ID = rid
        poll_progress._POLLS[rid] = {
            "run_id": rid,
            "finished": True,
            "overall_ok": True,
            "sources": [],
        }

    assert poll_progress.is_poll_running() is False

    with poll_progress._POLL_LOCK:
        assert poll_progress._ACTIVE_POLL_RUN_ID is None


def test_is_poll_running_false_when_state_missing():
    with poll_progress._POLL_LOCK:
        poll_progress._POLLS.clear()
        poll_progress._ACTIVE_POLL_RUN_ID = "orphan-no-dict"

    assert poll_progress.is_poll_running() is False

    with poll_progress._POLL_LOCK:
        assert poll_progress._ACTIVE_POLL_RUN_ID is None


@pytest.fixture(autouse=True)
def _cleanup_poll_globals():
    yield
    with poll_progress._POLL_LOCK:
        poll_progress._POLLS.clear()
        poll_progress._ACTIVE_POLL_RUN_ID = None
