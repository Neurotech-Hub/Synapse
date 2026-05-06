"""Public explore/search/home atlas tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.models import FundingOpportunity, Idea

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


def test_explore_search_and_homepage_spotlights(app, client):
    with app.app_context():
        db.session.add(
            Idea(
                slug="atlas_idea",
                title="Atlas Idea",
                status="public",
                is_public=True,
                is_reviewed=True,
                short_description="An atlas idea.",
            )
        )
        db.session.add(
            FundingOpportunity(
                slug="atlas_funding",
                title="Atlas Funding",
                status="active",
                is_public=True,
                is_reviewed=True,
                summary_public="Funding summary.",
            )
        )
        db.session.commit()

    home = client.get("/")
    assert home.status_code == 200
    assert b"Explore the Atlas" in home.data
    assert b"Atlas Idea" in home.data

    explore = client.get("/explore/")
    assert explore.status_code == 200
    assert b"Atlas Funding" in explore.data

    search = client.get("/search?q=Atlas")
    assert search.status_code == 200
    assert b"Atlas Idea" in search.data
    assert b"Atlas Funding" in search.data
