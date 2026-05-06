"""Dashboard review sections tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.models import FundingOpportunity, LLMRun, LeadReport, Person

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


def test_dashboard_renders_attention_sections(app, client):
    with app.app_context():
        db.session.add(FundingOpportunity(slug="fund", title="Funding", is_reviewed=False))
        person = Person(slug="lead-person", display_name="Lead Person")
        db.session.add(person)
        db.session.flush()
        db.session.add(LeadReport(target_person_id=person.id, status="ok"))
        db.session.add(
            LLMRun(
                prompt_name="funding_extract",
                prompt_version="1.0.0",
                provider="ollama",
                input_fingerprint="x",
                rendered_prompt_hash="y",
                status="failed",
            )
        )
        db.session.commit()

    _login(client)
    rv = client.get("/admin/")
    assert rv.status_code == 200
    assert b"Funding" in rv.data
    assert b"Lead candidates" in rv.data
    assert b"Lead Person" in rv.data
    assert b"LLM failures" in rv.data
    assert b"matching/edges" not in rv.data

    redirect = client.get("/admin/review", follow_redirects=False)
    assert redirect.status_code == 302
    assert (redirect.headers.get("Location") or "").endswith("/admin/")
