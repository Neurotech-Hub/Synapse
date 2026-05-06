"""Public explore/search/home tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.models import ContentItem, FundingOpportunity, LeadReport, MatchEdge, Organization, Person, Source

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


def test_explore_search_and_homepage_latest(app, client):
    with app.app_context():
        db.session.add(
            FundingOpportunity(
                slug="watched_funding",
                title="Watched Funding",
                status="active",
                is_public=True,
                is_reviewed=True,
                summary_public="Funding summary.",
            )
        )
        source = Source(url="https://example.org/feed", label="Example Lab", kind="rss_feed", enabled=True, pending=False)
        db.session.add(source)
        db.session.flush()
        db.session.add(ContentItem(source_id=source.id, external_id="signal-1", title="Watched Signal", snippet="A public signal."))
        db.session.commit()

    home = client.get("/")
    assert home.status_code == 200
    assert b"Tell us what to watch." in home.data
    assert b"The Latest" in home.data
    assert b"Watched Signal" in home.data
    assert b"Explore the Atlas" not in home.data
    assert b"Work with the Hub" not in home.data
    assert b"Request support" not in home.data

    explore = client.get("/explore/")
    assert explore.status_code == 200
    assert b"Watched Funding" in explore.data
    assert b"The Latest" in explore.data
    assert b"Watched Signal" in explore.data

    opportunities = client.get("/opportunities/")
    assert opportunities.status_code == 200
    assert b"Opportunities" in opportunities.data
    assert b"Watched Funding" in opportunities.data

    about = client.get("/about/")
    assert about.status_code == 410

    search = client.get("/search?q=Watched")
    assert search.status_code == 200
    assert b"Watched Funding" in search.data
    assert b"Signals" in search.data
    assert b"Watched Signal" in search.data


def test_public_atlas_excludes_private_admin_intelligence(app, client):
    with app.app_context():
        person = Person(slug="private-lead-person", display_name="Private Lead Person")
        db.session.add(person)
        db.session.flush()
        db.session.add(
            LeadReport(
                target_person_id=person.id,
                status="ok",
                executive_summary="Private candidate summary.",
                email_draft="Private next action.",
            )
        )
        db.session.add(
            FundingOpportunity(
                slug="public",
                title="Public Opportunity",
                status="active",
                is_public=True,
                is_reviewed=True,
                summary_public="Reviewed copy.",
                synthesized_json={"public_card": {"short_summary": "Draft synthesis copy"}},
                synthesis_status="needs_review",
            )
        )
        db.session.commit()

    for path in ["/", "/explore/", "/opportunities/", "/search?q=Private", "/funding/public"]:
        rv = client.get(path)
        assert rv.status_code == 200
        assert b"Private candidate summary" not in rv.data
        assert b"Private next action" not in rv.data
        assert b"Draft synthesis copy" not in rv.data


def test_person_and_organization_pages_do_not_depend_on_legacy_related_edges(app, client):
    with app.app_context():
        person = Person(slug="public-person", display_name="Public Person")
        org = Organization(slug="public-org", display_name="Public Org")
        funding = FundingOpportunity(
            slug="public-funding",
            title="Public Funding",
            status="active",
            is_public=True,
            is_reviewed=True,
            summary_public="Public funding copy.",
        )
        db.session.add_all([person, org, funding])
        db.session.flush()
        db.session.add_all(
            [
                Source(url="https://example.org/person", kind="html_page", enabled=True, pending=False, person_id=person.id),
                Source(url="https://example.org/org", kind="html_page", enabled=True, pending=False, organization_id=org.id),
                MatchEdge(source_type="funding", source_id=funding.id, target_type="person", target_id=person.id, match_type="funding_to_person", status="accepted", visibility="public"),
                MatchEdge(source_type="funding", source_id=funding.id, target_type="organization", target_id=org.id, match_type="funding_to_organization", status="accepted", visibility="private"),
            ]
        )
        db.session.commit()

    person_page = client.get("/people/public-person")
    assert person_page.status_code == 200
    assert b"Public Person" in person_page.data
    assert b"Public Funding" not in person_page.data
    assert b"Private rationale" not in person_page.data

    org_page = client.get("/organizations/public-org")
    assert org_page.status_code == 200
    assert b"Public Org" in org_page.data
    assert b"Public Funding" not in org_page.data
