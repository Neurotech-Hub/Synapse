"""Lightweight HTTP tests (in-memory SQLite)."""

import os

import pytest

from app import create_app
from app.extensions import db

pytestmark = pytest.mark.usefixtures("_admin_env")


@pytest.fixture(scope="module", autouse=True)
def _admin_env():
    os.environ["ADMIN_PASSWORD"] = "test-pass"
    yield


@pytest.fixture()
def app(tmp_path):
    flask_app = create_app()
    db_path = tmp_path / "test.db"
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        WTF_CSRF_ENABLED=False,
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


def test_public_submit_and_duplicate(client):
    r1 = client.post("/", data={"url": "https://example.edu/lab", "submit": "Submit"}, follow_redirects=True)
    assert r1.status_code == 200

    r2 = client.post("/", data={"url": "https://example.edu/lab", "submit": "Submit"})
    assert r2.status_code == 200
    assert b"already" in r2.data.lower()


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
