"""Public Funding Radar route tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.models import FundingOpportunity

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


def test_public_funding_only_shows_reviewed_public_records(app, client):
    with app.app_context():
        public = FundingOpportunity(
            slug="public_funding",
            title="Public Funding",
            sponsor_name="Example Sponsor",
            source_url="https://example.org/funding",
            status="active",
            is_public=True,
            is_reviewed=True,
            effort_index="moderate",
            amount_text="$100,000",
            deadline_text="Rolling",
            summary_public="Public funding summary.",
            notes_private="Private admin note must not appear.",
            topic_tags_json=["neurotechnology"],
        )
        private = FundingOpportunity(
            slug="private_funding",
            title="Private Funding",
            status="active",
            is_public=False,
            is_reviewed=True,
        )
        draft = FundingOpportunity(
            slug="draft_funding",
            title="Draft Funding",
            status="draft",
            is_public=True,
            is_reviewed=True,
        )
        db.session.add_all([public, private, draft])
        db.session.commit()

    index = client.get("/funding/")
    assert index.status_code == 200
    assert b"Funding Radar" in index.data
    assert b"Public Funding" in index.data
    assert b"Private Funding" not in index.data
    assert b"Draft Funding" not in index.data
    assert b"Effort: Moderate" in index.data

    detail = client.get("/funding/public_funding")
    assert detail.status_code == 200
    assert b"Public funding summary" in detail.data
    assert b"Open official source" in detail.data
    assert b"Private admin note" not in detail.data

    assert client.get("/funding/private_funding").status_code == 404
    assert client.get("/funding/draft_funding").status_code == 404


def test_public_funding_ignores_unapplied_synthesis_draft(app, client):
    with app.app_context():
        funding = FundingOpportunity(
            slug="draft_synthesis",
            title="Reviewed Funding",
            status="active",
            is_public=True,
            is_reviewed=True,
            summary_public="Reviewed public copy.",
            synthesized_json={"public_summary": "Unreviewed draft copy"},
            synthesis_status="needs_review",
        )
        db.session.add(funding)
        db.session.commit()

    detail = client.get("/funding/draft_synthesis")
    assert detail.status_code == 200
    assert b"Reviewed public copy" in detail.data
    assert b"Unreviewed draft copy" not in detail.data


def test_public_funding_can_be_disabled(tmp_path):
    db_file = tmp_path / "test.db"
    flask_app = create_app(
        override_config={
            "TESTING": True,
            "DEBUG": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
            "WTF_CSRF_ENABLED": False,
            "SYNAPSE_PUBLIC_FUNDING_ENABLED": False,
        },
    )
    with flask_app.app_context():
        db.create_all()
    client = flask_app.test_client()

    assert client.get("/funding/").status_code == 404


def test_public_ideas_route_is_removed(client):
    assert client.get("/ideas/").status_code == 404
