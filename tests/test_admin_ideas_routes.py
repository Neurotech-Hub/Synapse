"""Admin Idea workflow tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.models import Idea

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


def _login(client):
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )


def test_admin_can_create_edit_review_and_archive_idea(app, client):
    _login(client)

    created = client.post(
        "/admin/ideas/new",
        data={
            "title": "Automated Home-Cage Monitoring",
            "idea_type": "buildable_concept",
            "status": "draft",
            "short_description": "Continuous behavioral monitoring with embedded sensors.",
            "public_summary": "Public-safe overview.",
            "private_summary": "Private Hub fit note.",
            "tags": "behavior; embedded sensing",
            "aliases": "home-cage phenotyping; long-duration monitoring",
            "hub_capabilities": "embedded systems; data logging",
            "created_via": "manual",
            "submit": "Save",
        },
        follow_redirects=True,
    )

    assert created.status_code == 200
    assert b"Automated Home-Cage Monitoring" in created.data

    with app.app_context():
        idea = Idea.query.filter_by(slug="automated_home-cage_monitoring").one()
        idea_id = idea.id
        assert idea.tags_json == ["behavior", "embedded sensing"]
        assert idea.aliases_json == ["home-cage phenotyping", "long-duration monitoring"]

    reviewed = client.post(f"/admin/ideas/{idea_id}/review", follow_redirects=True)
    assert reviewed.status_code == 200

    edited = client.post(
        f"/admin/ideas/{idea_id}/edit",
        data={
            "title": "Automated Home-Cage Monitoring",
            "idea_type": "buildable_concept",
            "status": "public",
            "is_public": "y",
            "is_reviewed": "y",
            "short_description": "Continuous behavioral monitoring with embedded sensors.",
            "public_summary": "Reviewed public overview.",
            "private_summary": "Private Hub fit note.",
            "tags": "behavior; embedded sensing; data logging",
            "created_via": "manual",
            "submit": "Save",
        },
        follow_redirects=True,
    )

    assert edited.status_code == 200
    with app.app_context():
        saved = db.session.get(Idea, idea_id)
        assert saved.status == "public"
        assert saved.is_public is True
        assert saved.is_reviewed is True
        assert saved.reviewed_at is not None
        assert saved.tags_json == ["behavior", "embedded sensing", "data logging"]

    archived = client.post(f"/admin/ideas/{idea_id}/archive", follow_redirects=True)
    assert archived.status_code == 200
    with app.app_context():
        saved = db.session.get(Idea, idea_id)
        assert saved.status == "archived"
        assert saved.is_public is False
        assert saved.archived_at is not None


def test_admin_ideas_list_filters(app, client):
    with app.app_context():
        db.session.add_all(
            [
                Idea(
                    slug="public_resource",
                    title="Public Resource",
                    idea_type="public_resource_topic",
                    status="public",
                    is_public=True,
                    is_reviewed=True,
                ),
                Idea(slug="draft_theme", title="Draft Theme", idea_type="research_theme", status="draft"),
            ]
        )
        db.session.commit()

    _login(client)
    rv = client.get("/admin/ideas?status=public&visibility=public")
    assert rv.status_code == 200
    assert b"Public Resource" in rv.data
    assert b"Draft Theme" not in rv.data
