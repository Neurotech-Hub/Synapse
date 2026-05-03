"""Entity tagging on sources (shallow integration)."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.models import Entity, Source

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


def test_admin_source_entity_checkbox_roundtrip(app, client):
    with app.app_context():
        db.session.add(
            Source(
                url="https://example.org/track",
                kind="rss_feed",
                label=None,
                enabled=True,
                pending=False,
                lead_source=False,
            )
        )
        db.session.add(
            Entity(slug="test_lab", kind="lab", display_name="Test Lab", notes=None),
        )
        db.session.commit()
        sid = Source.query.filter_by(url="https://example.org/track").first().id
        eid = Entity.query.filter_by(slug="test_lab").first().id

    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )

    rv = client.get(f"/admin/sources/{sid}")
    assert rv.status_code == 200
    assert b"Tracked entities" in rv.data
    assert b"test_lab" in rv.data

    client.post(
        f"/admin/sources/{sid}",
        data={
            "url": "https://example.org/track",
            "kind": "rss_feed",
            "label": "",
            "hide_from_polling": "",
            "lead_source": "",
            "entity_ids": str(eid),
            "submit": "Save",
        },
        follow_redirects=True,
    )

    with app.app_context():
        src = db.session.get(Source, sid)
        assert len(src.entities) == 1
        assert src.entities[0].slug == "test_lab"

    rv2 = client.get(f"/admin/sources/{sid}")
    assert rv2.status_code == 200
    # Checkbox checked when re-rendered
    assert b'value="' + str(eid).encode() + b'"' in rv2.data and b"checked" in rv2.data


def test_entities_new_accept_title_case_slug(app, client):
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    rv = client.post(
        "/admin/entities/new",
        data={
            "kind": "lab",
            "display_name": "Washington Neuro Lab!",
            "notes": "",
            "submit": "Save",
        },
        follow_redirects=True,
    )
    assert rv.status_code == 200
    with app.app_context():
        row = Entity.query.filter_by(slug="washington_neuro_lab").first()
        assert row is not None
        assert row.display_name == "Washington Neuro Lab!"


def test_entities_new_shows_validation_when_display_yields_empty_slug(app, client):
    """Symbols-only display produces no usable slug."""
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    rv = client.post(
        "/admin/entities/new",
        data={
            "kind": "lab",
            "display_name": "%%%",
            "notes": "",
            "submit": "Save",
        },
        follow_redirects=False,
    )
    assert rv.status_code == 400
    assert b"Display name needs" in rv.data


def test_entities_second_same_display_name_gets_incremented_slug(app, client):
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )
    for _ in range(2):
        client.post(
            "/admin/entities/new",
            data={
                "kind": "lab",
                "display_name": "Duplicate Display",
                "notes": "",
                "submit": "Save",
            },
            follow_redirects=True,
        )
    with app.app_context():
        slugs = {e.slug for e in Entity.query.all()}
        assert "duplicate_display" in slugs
        assert "duplicate_display_2" in slugs
