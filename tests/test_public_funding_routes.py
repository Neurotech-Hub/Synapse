"""Public Funding Radar route tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.models import FundingOpportunity, Idea, MatchEdge

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


def test_public_idea_and_funding_show_public_safe_related_edges(app, client):
    with app.app_context():
        funding = FundingOpportunity(
            slug="related_funding",
            title="Related Funding",
            status="active",
            is_public=True,
            is_reviewed=True,
            effort_index="mild",
            summary_public="A public funding card.",
        )
        private_funding = FundingOpportunity(
            slug="private_related_funding",
            title="Private Related Funding",
            status="active",
            is_public=True,
            is_reviewed=True,
            summary_private="Should not appear.",
        )
        idea = Idea(
            slug="related_idea",
            title="Related Idea",
            status="public",
            is_public=True,
            is_reviewed=True,
            short_description="A public idea.",
        )
        private_idea = Idea(
            slug="private_idea",
            title="Private Idea",
            status="public",
            is_public=False,
            is_reviewed=True,
        )
        db.session.add_all([funding, private_funding, idea, private_idea])
        db.session.flush()
        db.session.add_all(
            [
                MatchEdge(
                    source_type="funding",
                    source_id=funding.id,
                    target_type="idea",
                    target_id=idea.id,
                    match_type="funding_to_idea",
                    status="accepted",
                    visibility="public_safe",
                    score_total=0.8,
                    private_rationale="Private rationale must not appear.",
                ),
                MatchEdge(
                    source_type="funding",
                    source_id=private_funding.id,
                    target_type="idea",
                    target_id=idea.id,
                    match_type="funding_to_idea",
                    status="accepted",
                    visibility="private",
                    score_total=0.9,
                ),
                MatchEdge(
                    source_type="funding",
                    source_id=funding.id,
                    target_type="idea",
                    target_id=private_idea.id,
                    match_type="funding_to_idea",
                    status="accepted",
                    visibility="public_safe",
                    score_total=0.9,
                ),
            ]
        )
        db.session.commit()

    idea_detail = client.get("/ideas/related_idea")
    assert idea_detail.status_code == 200
    assert b"Related Funding" in idea_detail.data
    assert b"Private Related Funding" not in idea_detail.data
    assert b"Private rationale" not in idea_detail.data

    funding_detail = client.get("/funding/related_funding")
    assert funding_detail.status_code == 200
    assert b"Related Idea" in funding_detail.data
    assert b"Private Idea" not in funding_detail.data
