"""LLMRun logging helper tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.llm.run import complete_llm_run, create_llm_run, fail_llm_run
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


def test_create_and_complete_llm_run(app):
    with app.app_context():
        run, rendered = create_llm_run(
            "funding_public_card",
            {"funding_json": {"title": "Seed"}, "schema": {"display_title": ""}},
            source_type="funding",
            source_id=7,
        )
        assert run.id is not None
        assert "Seed" in rendered
        assert run.prompt_version == "1.0.0"
        assert run.provider == "ollama"
        assert run.estimated_input_tokens > 0

        complete_llm_run(run, '{"schema_version":"1.0"}', validation_errors=["missing title"])
        db.session.commit()

        saved = db.session.get(LLMRun, run.id)
        assert saved.status == "validation_failed"
        assert saved.output_hash
        assert saved.validation_errors_json == ["missing title"]
        assert saved.completed_at is not None


def test_fail_llm_run(app):
    with app.app_context():
        run, _rendered = create_llm_run(
            "json_repair",
            {"schema": {}, "malformed_output": "{bad"},
            provider="openai",
        )
        fail_llm_run(run, "network error", latency_ms=123)
        db.session.commit()

        saved = db.session.get(LLMRun, run.id)
        assert saved.status == "failed"
        assert saved.error_message == "network error"
        assert saved.latency_ms == 123
