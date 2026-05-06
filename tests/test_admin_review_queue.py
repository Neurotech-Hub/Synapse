"""Admin review queue tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.models import FundingOpportunity, IdeaSuggestion, LLMRun, MatchEdge

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


def test_admin_review_queue_renders_all_sections(app, client):
    with app.app_context():
        db.session.add(FundingOpportunity(slug="fund", title="Funding", is_reviewed=False))
        db.session.add(IdeaSuggestion(source_type="content_item", source_id=1, title="Idea suggestion"))
        db.session.add(MatchEdge(source_type="funding", source_id=1, target_type="idea", target_id=1, match_type="funding_to_idea"))
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
    rv = client.get("/admin/review")
    assert rv.status_code == 200
    assert b"Funding" in rv.data
    assert b"Idea suggestion" in rv.data
    assert b"LLM failures" in rv.data
