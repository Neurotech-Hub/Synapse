"""Lightweight HTTP tests (in-memory SQLite)."""

import os
from unittest.mock import patch

import pytest

from app import create_app
from app.extensions import db
from app.models import PollLog, Source

pytestmark = pytest.mark.usefixtures("_admin_env")


@pytest.fixture(scope="module", autouse=True)
def _admin_env():
    os.environ["ADMIN_PASSWORD"] = "test-pass"
    yield


@pytest.fixture()
def app(tmp_path):
    db_file = tmp_path / "test.db"
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


def test_public_home(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Synapse" in resp.data


def test_public_submit_and_duplicate(app, client):
    r1 = client.post(
        "/",
        data={"url": "https://example.edu/lab", "ownership_intent": "organization", "submit": "Add"},
        follow_redirects=True,
    )
    assert r1.status_code == 200

    with app.app_context():
        row = Source.query.filter_by(url="https://example.edu/lab").first()
        assert row is not None
        assert row.pending is True
        assert row.enabled is True
        assert row.ownership_hint == "organization"

    r2 = client.post("/", data={"url": "https://example.edu/lab", "submit": "Add"})
    assert r2.status_code == 200
    assert b"already" in r2.data.lower()


def test_admin_sources_view_ok(app, client):
    with app.app_context():
        db.session.add(
            Source(
                url="https://example.net/feed.xml",
                kind="rss_feed",
                enabled=True,
                pending=False,
            )
        )
        db.session.commit()
        sid = Source.query.filter_by(url="https://example.net/feed.xml").first().id

    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    r = client.get(f"/admin/sources/{sid}")
    assert r.status_code == 200
    assert b"Settings" in r.data
    assert b"Snapshots" in r.data
    assert b"Content items" in r.data


def test_sources_list_shows_label_after_save(app, client):
    with app.app_context():
        db.session.add(
            Source(
                url="https://label-test.example/w",
                kind="html_page",
                enabled=True,
                pending=False,
            )
        )
        db.session.commit()
        sid = Source.query.filter_by(url="https://label-test.example/w").first().id

    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    client.post(
        f"/admin/sources/{sid}",
        data={
            "url": "https://label-test.example/w",
            "label": "Winter lab news",
            "kind": "html_page",
            "hide_from_polling": "",
            "submit": "Save",
        },
        follow_redirects=True,
    )
    r = client.get("/admin/sources")
    assert r.status_code == 200
    assert b"Winter lab news" in r.data


def test_admin_sources_snapshots_page(app, client):
    """Dedicated snapshots listing for one source."""
    with app.app_context():
        db.session.add(
            Source(
                url="https://example.org/page",
                kind="html_page",
                enabled=True,
                pending=False,
            )
        )
        db.session.commit()
        sid = Source.query.filter_by(url="https://example.org/page").first().id

    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    r = client.get(f"/admin/sources/{sid}/snapshots", follow_redirects=False)
    assert r.status_code == 200
    assert b"Snapshots" in r.data
    assert str(sid).encode() in r.data


def test_admin_sources_edit_legacy_redirect(app, client):
    with app.app_context():
        db.session.add(
            Source(
                url="https://example.invalid/x",
                kind="html_page",
                enabled=True,
                pending=False,
            )
        )
        db.session.commit()
        sid = Source.query.filter_by(url="https://example.invalid/x").first().id

    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    r = client.get(f"/admin/sources/{sid}/edit", follow_redirects=False)
    assert r.status_code == 302
    assert f"/admin/sources/{sid}" in (r.headers.get("Location") or "")


def test_admin_source_disapprove(app, client):
    with app.app_context():
        db.session.add(
            Source(
                url="https://example.org/tracked",
                kind="html_page",
                enabled=True,
                pending=False,
            )
        )
        db.session.commit()
        sid = Source.query.filter_by(url="https://example.org/tracked").first().id

    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    r = client.post(
        f"/admin/sources/{sid}/disapprove",
        follow_redirects=True,
    )
    assert r.status_code == 200
    with app.app_context():
        row = db.session.get(Source, sid)
        assert row.pending is True


def test_admin_snapshots_all_ok(client):
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    r = client.get("/admin/snapshots")
    assert r.status_code == 200
    assert b"Snapshots" in r.data


def test_dashboard_lists_pending_public_source(client):
    client.post(
        "/",
        data={"url": "https://pending.example.edu/page", "submit": "Add"},
        follow_redirects=True,
    )
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    r = client.get("/admin/")
    assert r.status_code == 200
    assert b"Sources awaiting approval" in r.data
    assert b"pending.example.edu" in r.data
    assert b"View to assign" in r.data


def test_content_items_list_shows_bulk_html_refresh(client):
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    r = client.get("/admin/items")
    assert r.status_code == 200
    assert b"Refresh all HTML content" in r.data


def test_items_refresh_all_html_snippets_no_html_sources(client):
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    with patch("app.web.admin.routes.refresh_html_page_content_items") as mock_batch:
        r = client.post("/admin/items/refresh-all-html-snippets", follow_redirects=True)
        mock_batch.assert_not_called()
    assert r.status_code == 200
    assert b"No HTML page sources" in r.data


def test_items_refresh_all_html_snippets_batches(app, client):
    with app.app_context():
        db.session.add(
            Source(
                url="https://bulk-refresh.example/page",
                kind="html_page",
                enabled=True,
                pending=False,
            )
        )
        db.session.commit()
        sid = Source.query.filter_by(url="https://bulk-refresh.example/page").first().id

    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    with patch("app.web.admin.routes.refresh_html_page_content_items") as mock_batch:
        mock_batch.return_value = [{"status": "updated", "source_id": sid}]
        r = client.post(
            f"/admin/items/refresh-all-html-snippets?source_id={sid}",
            follow_redirects=True,
        )
        mock_batch.assert_called_once()
        assert list(mock_batch.call_args[0][0]) == [sid]
    assert r.status_code == 200
    assert b"Ran HTML re-fetch" in r.data


def test_leads_page_has_pipeline_settings(client):
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    r = client.get("/admin/leads")
    assert r.status_code == 200
    assert b"Hub settings" in r.data
    assert b"Save Hub settings" in r.data
    assert b"Recent lead report logs" in r.data


def test_dashboard_filters_lead_job_poll_logs(app, client):
    with app.app_context():
        db.session.add(
            PollLog(
                detail="[lead-qual] UNIQUE_QUAL_LOG_SNIP_991",
                ok=True,
            )
        )
        db.session.add(
            PollLog(
                detail="[lead-report] UNIQUE_REPORT_LOG_SNIP_774",
                ok=True,
            )
        )
        db.session.add(
            PollLog(
                detail="UNIQUE_INGEST_LOG_SNIP_882",
                ok=True,
            )
        )
        db.session.commit()

    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    r = client.get("/admin/")
    assert r.status_code == 200
    assert b"UNIQUE_INGEST_LOG_SNIP_882" in r.data
    assert b"UNIQUE_QUAL_LOG_SNIP_991" not in r.data
    assert b"UNIQUE_REPORT_LOG_SNIP_774" not in r.data

    r_leads = client.get("/admin/leads")
    assert r_leads.status_code == 200
    assert b"UNIQUE_REPORT_LOG_SNIP_774" in r_leads.data
    assert b"UNIQUE_QUAL_LOG_SNIP_991" not in r_leads.data


def test_admin_sidebar_sources_nested_nav(client):
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    r = client.get("/admin/")
    assert r.status_code == 200
    assert b"admin-sidebar-group" in r.data
    assert b"/admin/items" in r.data
    assert b"/admin/snapshots" in r.data


def test_admin_login_redirect(client):
    r = client.get("/admin/")
    assert r.status_code == 302

    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    r = client.get("/admin/")
    assert r.status_code == 200
    assert b"LLM:" in r.data
