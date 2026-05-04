"""Public Latest LLM curation (fingerprints, read path, batch apply)."""

from __future__ import annotations

import os
import threading
from collections import deque
from unittest.mock import patch

import pytest

from app import create_app
from app.domain.public_feed_display import (
    collapse_obvious_doubled_title,
    effective_public_latest_snippet,
    effective_public_latest_title,
    heuristic_uncurated_hide_from_public_latest,
    strip_nav_accessibility_prefixes,
    utility_url_path_suppresses_public_latest,
)
from app.extensions import db
from app.models import ContentItem, Source
from app.public_feed.curate import public_feed_input_fingerprint, run_public_feed_curation_batch
from app.public_feed.curate_progress import snapshot_public_feed_curation, start_background_public_feed_curation
from app.web.public_routes import _latest_feed_groups

pytestmark = pytest.mark.usefixtures("_admin_env")


@pytest.fixture(scope="module", autouse=True)
def _admin_env():
    os.environ["ADMIN_PASSWORD"] = "test-pass"
    yield


@pytest.fixture()
def app(tmp_path):
    db_file = tmp_path / "pf.db"
    flask_app = create_app(
        override_config={
            "TESTING": True,
            "DEBUG": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
            "WTF_CSRF_ENABLED": False,
        },
    )
    with flask_app.app_context():
        db.create_all()
        yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


def _approved_source():
    return Source(
        url="https://example.org/public-feed-test",
        kind="rss_feed",
        enabled=True,
        pending=False,
    )


def test_public_feed_input_fingerprint_changes_with_title(app):
    with app.app_context():
        s = _approved_source()
        db.session.add(s)
        db.session.flush()
        ci = ContentItem(
            source_id=s.id,
            external_id="entry:1",
            title="Alpha",
            link="https://example.org/a",
            snippet="S1",
        )
        db.session.add(ci)
        db.session.commit()
        fp1 = public_feed_input_fingerprint(ci)
        ci.title = "Beta"
        fp2 = public_feed_input_fingerprint(ci)
        assert fp1 != fp2
        assert len(fp1) == 64


def test_strip_nav_accessibility_prefixes():
    raw = "Skip to content Skip to search Skip to footer Department of Neuroscience"
    assert strip_nav_accessibility_prefixes(raw).startswith("Department")


def test_utility_path_suppresses_about_us_even_when_curated_show(app):
    with app.app_context():
        s = _approved_source()
        db.session.add(s)
        db.session.flush()
        ci = ContentItem(
            source_id=s.id,
            external_id="about",
            title="About Us",
            link="https://neurotechhub.wustl.edu/about-us/",
            snippet="Skip to content Skip to search",
        )
        assert utility_url_path_suppresses_public_latest(ci) is True
        assert heuristic_uncurated_hide_from_public_latest(ci) is False
        ci.public_feed_verdict = "show"
        assert utility_url_path_suppresses_public_latest(ci) is True


def test_effective_snippet_strips_skip_prefix_without_verdict(app):
    with app.app_context():
        s = _approved_source()
        db.session.add(s)
        db.session.flush()
        ci = ContentItem(
            source_id=s.id,
            external_id="snip",
            title="Real paper",
            link="https://pubmed.ncbi.nlm.nih.gov/1/",
            snippet="Skip to content Abstract Lorem ipsum dolor sit amet.",
        )
        db.session.add(ci)
        db.session.commit()
        out = effective_public_latest_snippet(ci)
        assert out is not None
        assert "Skip to" not in out
        assert out.startswith("Abstract")


def test_collapse_doubled_title_and_effective_display(app):
    with app.app_context():
        s = _approved_source()
        db.session.add(s)
        db.session.flush()
        ci = ContentItem(
            source_id=s.id,
            external_id="entry:2",
            title="About UsAbout Us",
            link="https://example.org/b",
            snippet="nav",
        )
        assert collapse_obvious_doubled_title(ci.title) == "About Us"
        assert effective_public_latest_title(ci) == "About Us"
        ci.public_feed_verdict = "show"
        ci.public_feed_display_title = "Clean"
        assert effective_public_latest_title(ci) == "Clean"


def test_latest_feed_groups_drops_hide(app):
    with app.app_context():
        s = _approved_source()
        db.session.add(s)
        db.session.flush()
        shown = ContentItem(
            source_id=s.id,
            external_id="entry:show",
            title="Keep me",
            link="https://example.org/keep",
            snippet="ok",
            public_feed_verdict="show",
        )
        hidden = ContentItem(
            source_id=s.id,
            external_id="entry:hide",
            title="Hide me",
            link="https://example.org/hide",
            snippet="x",
            public_feed_verdict="hide",
        )
        db.session.add_all([shown, hidden])
        db.session.commit()
        shown_id, hidden_id = int(shown.id), int(hidden.id)

    with app.test_request_context("/"):
        groups, _label = _latest_feed_groups()
    flat = []
    for g in groups:
        if g["kind"] == "single":
            flat.append(g["item"].id)
        else:
            for it in g["batch_items"]:
                flat.append(it.id)
    assert hidden_id not in flat
    assert shown_id in flat


def test_run_public_feed_curation_batch_mocked_llm(app):
    with app.app_context():
        s = _approved_source()
        db.session.add(s)
        db.session.flush()
        a = ContentItem(
            source_id=s.id,
            external_id="a",
            title="T1",
            link="https://example.org/1",
            snippet="S",
        )
        b = ContentItem(
            source_id=s.id,
            external_id="b",
            title="T2",
            link="https://example.org/2",
            snippet="S",
        )
        db.session.add_all([a, b])
        db.session.commit()
        aid, bid = int(a.id), int(b.id)

    fake = {
        "results": [
            {"content_item_id": aid, "verdict": "show", "display_title": "One", "display_blurb": "Blurb"},
            {"content_item_id": bid, "verdict": "hide"},
        ]
    }
    with app.app_context(), patch("app.public_feed.curate.run_public_feed_curate_llm", return_value=fake):
        out = run_public_feed_curation_batch(limit=10, commit=True)
    assert out["status"] == "ok"
    assert out["shown"] == 1
    assert out["hidden"] == 1

    with app.app_context():
        ra = db.session.get(ContentItem, aid)
        rb = db.session.get(ContentItem, bid)
        assert ra is not None and rb is not None
        assert ra.public_feed_verdict == "show"
        assert ra.public_feed_display_title == "One"
        assert ra.public_feed_display_blurb == "Blurb"
        assert ra.public_feed_input_fingerprint == public_feed_input_fingerprint(ra)
        assert rb.public_feed_verdict == "hide"
        assert rb.public_feed_display_title is None


def test_digest_page_shows_public_feed_section(client):
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    r = client.get("/admin/digest")
    assert r.status_code == 200
    assert b"Curate public feed" in r.data
    assert b"Uncurated public Latest candidates" in r.data
    assert b"every" in r.data.lower()


def test_digest_public_feed_curate_status_unknown(client):
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    r = client.get("/admin/digest/public-feed-curate-status?run_id=nope")
    assert r.status_code == 404


def test_digest_curate_post_redirects_with_run_id(client):
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    with patch(
        "app.web.admin.routes.start_background_public_feed_curation",
        return_value=("run-xyz-1", ""),
    ):
        r = client.post(
            "/admin/digest/curate-public-feed",
            data={},
            follow_redirects=False,
        )
    assert r.status_code == 302
    loc = r.headers.get("Location") or ""
    assert "feed_curate_run=run-xyz-1" in loc


class _ImmediateThread:
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
        self._target = target
        self.daemon = daemon

    def start(self) -> None:
        if self._target:
            self._target()


def test_background_public_feed_curation_runs_multiple_batches(app, monkeypatch):
    monkeypatch.setattr(threading, "Thread", _ImmediateThread)
    calls = {"n": 0}

    def fake_batch(*, limit: int, commit: bool):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"status": "ok", "processed": 2, "shown": 1, "hidden": 1}
        if calls["n"] == 2:
            return {"status": "ok", "processed": 1, "shown": 1, "hidden": 0}
        return {"status": "empty", "processed": 0, "shown": 0, "hidden": 0}

    count_returns = deque([3, 1, 1, 0, 0, 0, 0])

    def fake_count() -> int:
        return int(count_returns.popleft() if count_returns else 0)

    monkeypatch.setattr("app.public_feed.curate.count_uncurated_public_feed_candidates", fake_count)
    monkeypatch.setattr("app.public_feed.curate.run_public_feed_curation_batch", fake_batch)

    rid, err = start_background_public_feed_curation(app)
    assert err == ""
    assert rid
    snap = snapshot_public_feed_curation(rid)
    assert snap is not None
    assert snap["finished"] is True
    assert snap["batches_completed"] == 2
    assert snap["total_processed"] == 3
    assert calls["n"] == 2
