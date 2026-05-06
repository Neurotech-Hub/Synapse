"""Sprint 04A UX simplification route/template tests."""

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


def _login(client):
    client.post("/admin/login", data={"password": "test-pass", "submit": "Sign in"}, follow_redirects=True)


def test_public_nav_is_experience_oriented(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert b"Explore" in rv.data
    assert b"Opportunities" in rv.data
    assert b"Tell us what to watch." in rv.data
    assert b"About" not in rv.data
    assert b"Say Hello" in rv.data
    assert b"mailto:gaidica@wustl.edu" in rv.data
    assert b"Work with the Hub" not in rv.data
    assert b">People</a>" not in rv.data
    assert b">Organizations</a>" not in rv.data
    assert client.get("/people/").status_code == 200
    assert client.get("/organizations/").status_code == 200


def test_admin_nav_is_workflow_grouped(client):
    _login(client)
    rv = client.get("/admin/")
    assert rv.status_code == 200
    assert b"Dashboard" in rv.data
    assert b"Data" in rv.data
    assert b"Content items" in rv.data
    assert b"Snapshots" in rv.data
    assert b"Places" in rv.data
    assert b"Tools" in rv.data
    assert b"Leads" in rv.data
    assert b"Inbox" not in rv.data
    assert b"Atlas" not in rv.data
    assert b"Intake" not in rv.data
    assert rv.data.count(b">Sources</a>") == 1
    assert b"Settings" in rv.data
    assert b"Relationships" not in rv.data
    assert b"Hypotheses" not in rv.data


def test_funding_detail_stage_and_advanced_tools(app, client):
    with app.app_context():
        funding = FundingOpportunity(slug="stage", title="Stage Funding", source_url="https://example.org")
        db.session.add(funding)
        db.session.commit()
        funding_id = funding.id

    _login(client)
    rv = client.get(f"/admin/funding/{funding_id}")
    assert rv.status_code == 200
    assert b"Funding workflow" in rv.data
    assert b"Needs source" in rv.data
    assert b"Read from source link" in rv.data
    assert b"Advanced Tools" in rv.data
    assert b"Private" in rv.data
    assert b"Needs review" in rv.data


def test_funding_publish_action_makes_reviewed_private_card_public(app, client):
    with app.app_context():
        funding = FundingOpportunity(
            slug="publishable",
            title="Publishable Funding",
            status="draft",
            is_reviewed=True,
            is_public=False,
            raw_text="source text",
            synthesized_json={"public_card": {"short_summary": "Draft summary"}},
        )
        db.session.add(funding)
        db.session.commit()
        funding_id = funding.id

    _login(client)
    detail = client.get(f"/admin/funding/{funding_id}")
    assert detail.status_code == 200
    assert b"Ready to publish" in detail.data
    assert b"Publish card" in detail.data
    assert f"/admin/funding/{funding_id}/review".encode() not in detail.data

    published = client.post(f"/admin/funding/{funding_id}/publish", follow_redirects=True)
    assert published.status_code == 200
    with app.app_context():
        saved = db.session.get(FundingOpportunity, funding_id)
        assert saved.is_public is True
        assert saved.is_reviewed is True
        assert saved.status == "active"
