"""Idea model tests."""

import os

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.ideas.service import allocate_idea_slug, idea_is_publicly_visible, parse_semicolon_list
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


def test_idea_allows_manual_minimum_record(app):
    with app.app_context():
        idea = Idea(
            slug="home_cage_monitoring",
            title="Home-cage monitoring",
            idea_type="buildable_concept",
            short_description="Continuous behavioral monitoring in home cages.",
        )
        db.session.add(idea)
        db.session.commit()

        saved = Idea.query.filter_by(slug="home_cage_monitoring").one()
        assert saved.status == "draft"
        assert saved.created_via == "manual"
        assert saved.is_public is False
        assert saved.tags_json == []


def test_idea_rejects_invalid_status(app):
    with app.app_context():
        idea = Idea(slug="bad_status", title="Bad Status", status="published")
        db.session.add(idea)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_idea_slug_allocation_and_list_parsing(app):
    with app.app_context():
        db.session.add(Idea(slug="closed_loop", title="Closed loop"))
        db.session.commit()

        assert allocate_idea_slug("Closed loop") == "closed_loop_2"
        assert parse_semicolon_list("sensing; behavior ; sensing") == ["sensing", "behavior"]


def test_idea_public_visibility_requires_public_reviewed_status(app):
    public_idea = Idea(
        slug="public_idea",
        title="Public Idea",
        status="public",
        is_public=True,
        is_reviewed=True,
    )
    draft_idea = Idea(slug="draft_idea", title="Draft Idea", status="draft", is_public=True, is_reviewed=True)

    assert idea_is_publicly_visible(public_idea) is True
    assert idea_is_publicly_visible(draft_idea) is False
