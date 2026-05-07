"""Generic LLM execution pipeline tests using mock providers only."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.llm.execute import execute_prompt
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
            "SYNAPSE_LLM_SYNTHESIS_ENABLED": True,
            "SYNAPSE_MAX_PROMPT_CHARS": 24_000,
            "SYNAPSE_OPENAI_ESCALATION_ENABLED": False,
        },
    )
    with flask_app.app_context():
        db.create_all()
        yield flask_app


def _funding_card_vars(title: str = "Pilot Award") -> dict:
    return {
        "funding_json": {"title": title},
        "schema": {
            "schema_version": "1.0",
            "display_title": "",
            "short_summary": "",
            "effort_label": "mild|moderate|heavy|unknown",
            "confidence": 0.0,
            "not_enough_information": False,
        },
    }


def test_execute_prompt_mock_success_creates_completed_run(app):
    with app.app_context():
        result = execute_prompt(
            "funding_public_card",
            _funding_card_vars(),
            provider="mock",
            source_type="funding",
            source_id=1,
            mock_provider=lambda prompt, model: (
                '{"schema_version":"1.0","display_title":"Pilot Award","short_summary":"A short summary.",'
                '"effort_label":"mild","confidence":0.9,"not_enough_information":false,'
                '"best_for":[],"tags":[],"missing_information":[],"warnings":[]}'
            ),
        )

        assert result.ok
        assert result.data["display_title"] == "Pilot Award"
        run = db.session.get(LLMRun, result.run.id)
        assert run.status == "ok"
        assert run.provider == "mock"
        assert run.output_hash
        assert run.source_type == "funding"
        assert run.source_id == 1


def test_execute_prompt_validation_failure_logs_run(app):
    with app.app_context():
        result = execute_prompt(
            "funding_effort_classify",
            {
                "schema": {},
                "funding_extraction_json": {"title": "X"},
                "heuristic_effort_guess": "unknown",
                "heuristic_rationale": "",
            },
            provider="mock",
            mock_provider=lambda prompt, model: (
                '{"schema_version":"1.0","effort_index":"none","effort_rationale":"bad","confidence":0.8,'
                '"missing_information":[],"warnings":[]}'
            ),
        )

        assert not result.ok
        assert any("Invalid effort_index" in err for err in result.errors)
        run = db.session.get(LLMRun, result.run.id)
        assert run.status == "validation_failed"
        assert run.validation_errors_json


def test_execute_prompt_provider_exception_logs_failed(app):
    def boom(prompt, model):
        raise RuntimeError("provider broke")

    with app.app_context():
        result = execute_prompt(
            "funding_public_card",
            _funding_card_vars(),
            provider="mock",
            mock_provider=boom,
        )

        assert not result.ok
        run = db.session.get(LLMRun, result.run.id)
        assert run.status == "failed"
        assert "provider broke" in run.error_message


def test_execute_prompt_enforces_prompt_size(app):
    with app.app_context():
        result = execute_prompt(
            "funding_public_card",
            _funding_card_vars("X" * 30_000),
            provider="ollama",
            mock_provider=None,
        )

        assert not result.ok
        assert any("SYNAPSE_MAX_PROMPT_CHARS" in err for err in result.errors)
        assert LLMRun.query.count() == 0


def test_execute_prompt_blocks_openai_by_default(app):
    with app.app_context():
        result = execute_prompt(
            "funding_public_card",
            _funding_card_vars(),
            provider="openai",
            mock_provider=None,
        )

        assert not result.ok
        assert any("OpenAI execution is disabled" in err for err in result.errors)
        assert LLMRun.query.count() == 0


def test_execute_prompt_disabled_flag_blocks_live_non_mock(tmp_path):
    db_file = tmp_path / "test.db"
    flask_app = create_app(
        override_config={
            "TESTING": True,
            "DEBUG": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
            "WTF_CSRF_ENABLED": False,
            "SYNAPSE_LLM_SYNTHESIS_ENABLED": False,
        },
    )
    with flask_app.app_context():
        db.create_all()
        result = execute_prompt("funding_public_card", _funding_card_vars(), provider="ollama")

        assert not result.ok
        assert any("LLM synthesis is disabled" in err for err in result.errors)
