"""Read-only retrieval facade (DB-backed)."""

from __future__ import annotations

import pytest

from app import create_app
from app.extensions import db
from app.identity import retrieval_facade as rf

pytestmark = pytest.mark.usefixtures("_admin_env")


@pytest.fixture(scope="module", autouse=True)
def _admin_env():
    import os

    os.environ.setdefault("ADMIN_PASSWORD", "test-pass")
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


def test_source_ids_person_empty(app) -> None:
    with app.app_context():
        assert rf.source_ids_for_entity("person", 999_999_999) == []


def test_get_entity_persona_snapshot_not_found(app) -> None:
    with app.app_context():
        out = rf.get_entity_persona_snapshot("person", 999_999_999)
        assert out.get("error") == "not_found"


def test_json_dumps_roundtrip(app) -> None:
    with app.app_context():
        s = rf.json_dumps({"a": 1})
        assert '"a": 1' in s


def test_openai_company_knowledge_search_shape(app) -> None:
    import json

    with app.app_context():
        s = rf.openai_company_knowledge_search_text("ab", entity_type="person", entity_id=999_999_999)
        d = json.loads(s)
        assert "results" in d and isinstance(d["results"], list)
