"""Admin Settings route tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.models import LLMRun

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


def test_admin_settings_shows_flags_caps_and_recent_runs(app, client):
    with app.app_context():
        db.session.add(
            LLMRun(
                prompt_name="funding_extract",
                prompt_version="1.0.0",
                provider="ollama",
                input_fingerprint="x" * 64,
                rendered_prompt_hash="y" * 64,
                status="failed",
                source_type="funding",
                source_id=1,
            )
        )
        db.session.commit()

    _login(client)
    rv = client.get("/admin/settings")

    assert rv.status_code == 200
    assert b"Feature flags" in rv.data
    assert b"Provider status" in rv.data
    assert b"Call caps" in rv.data
    assert b"Idea extraction from persona" not in rv.data
    assert b"idea_extract_from_persona" not in rv.data
    assert b"SYNAPSE_LLM_IDEA_EXTRACT_FROM_PERSONA_PROVIDER" not in rv.data
    assert b"Public Ideas" not in rv.data
    assert b"SYNAPSE_PUBLIC_IDEAS_ENABLED" not in rv.data
    assert b"funding_extract" in rv.data
    assert b"SYNAPSE_PUBLIC_FUNDING_ENABLED" in rv.data
