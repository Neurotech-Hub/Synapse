"""Public Ideas route tests."""

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


def test_public_ideas_only_show_reviewed_public_ideas(app, client):
    with app.app_context():
        db.session.add_all(
            [
                Idea(
                    slug="public_idea",
                    title="Public Idea",
                    idea_type="technical_capability",
                    status="public",
                    is_public=True,
                    is_reviewed=True,
                    short_description="Public-safe description.",
                    public_summary="Public-safe overview.",
                    private_summary="Private lead logic must not appear.",
                    tags_json=["sensing", "behavior"],
                ),
                Idea(
                    slug="private_idea",
                    title="Private Idea",
                    status="public",
                    is_public=False,
                    is_reviewed=True,
                ),
                Idea(
                    slug="draft_idea",
                    title="Draft Idea",
                    status="draft",
                    is_public=True,
                    is_reviewed=True,
                ),
            ]
        )
        db.session.commit()

    index = client.get("/ideas/")
    assert index.status_code == 200
    assert b"Public Idea" in index.data
    assert b"Private Idea" not in index.data
    assert b"Draft Idea" not in index.data

    detail = client.get("/ideas/public_idea")
    assert detail.status_code == 200
    assert b"Public-safe overview" in detail.data
    assert b"Private lead logic" not in detail.data

    assert client.get("/ideas/private_idea").status_code == 404
    assert client.get("/ideas/draft_idea").status_code == 404


def test_public_ideas_can_be_disabled(tmp_path):
    db_file = tmp_path / "test.db"
    flask_app = create_app(
        override_config={
            "TESTING": True,
            "DEBUG": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
            "WTF_CSRF_ENABLED": False,
            "SYNAPSE_IDEAS_ENABLED": False,
        },
    )
    with flask_app.app_context():
        db.create_all()
    client = flask_app.test_client()

    assert client.get("/ideas/").status_code == 404
