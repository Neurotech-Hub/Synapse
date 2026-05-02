"""Lightweight HTTP tests (in-memory SQLite)."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.models import Source

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
    r1 = client.post("/", data={"url": "https://example.edu/lab", "submit": "Add"}, follow_redirects=True)
    assert r1.status_code == 200

    with app.app_context():
        row = Source.query.filter_by(url="https://example.edu/lab").first()
        assert row is not None
        assert row.pending is True
        assert row.enabled is True

    r2 = client.post("/", data={"url": "https://example.edu/lab", "submit": "Add"})
    assert r2.status_code == 200
    assert b"already" in r2.data.lower()


def test_admin_sources_view_ok(app, client):
    with app.app_context():
        db.session.add(
            Source(
                url="https://example.net/feed.xml",
                kind="rss_feed",
                label="Test feed",
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


def test_admin_snapshots_legacy_redirect_hashes_fragment(app, client):
    """Old /snapshots URL lands on unified source view (#snapshots in Location)."""
    with app.app_context():
        db.session.add(
            Source(
                url="https://example.org/page",
                kind="html_page",
                label=None,
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
    assert r.status_code == 302
    assert f"/admin/sources/{sid}#snapshots" in r.headers.get("Location", "")


def test_admin_sources_edit_legacy_redirect(app, client):
    with app.app_context():
        db.session.add(
            Source(
                url="https://example.invalid/x",
                kind="html_page",
                label=None,
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
                label=None,
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
