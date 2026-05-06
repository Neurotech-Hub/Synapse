"""Admin ContentItem to IdeaSuggestion route tests."""

import os
from unittest.mock import patch

import pytest

from app import create_app
from app.extensions import db
from app.models import ContentItem, IdeaSuggestion, Source

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


def test_admin_generates_ideas_from_content_item(app, client):
    with app.app_context():
        src = Source(url="https://example.org", kind="html_page")
        db.session.add(src)
        db.session.flush()
        item = ContentItem(source_id=src.id, external_id="x", title="Behavior item", snippet="behavior sensing")
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    _login(client)

    def fake_generate(content_item_id, **kwargs):
        with app.app_context():
            db.session.add(IdeaSuggestion(source_type="content_item", source_id=content_item_id, title="Behavior Idea"))
            db.session.commit()

        class Result:
            ok = True
            errors = []

        return Result()

    with patch("app.web.admin.routes.generate_idea_suggestions_from_content_item", side_effect=fake_generate):
        rv = client.post(f"/admin/ideas/suggestions/generate/content-item/{item_id}", follow_redirects=True)

    assert rv.status_code == 200
    assert b"Behavior Idea" in rv.data
    with app.app_context():
        assert IdeaSuggestion.query.filter_by(source_type="content_item", source_id=item_id).count() == 1


def test_content_item_detail_has_generate_action(app, client):
    with app.app_context():
        src = Source(url="https://example.org", kind="html_page")
        db.session.add(src)
        db.session.flush()
        item = ContentItem(source_id=src.id, external_id="x", title="Behavior item", snippet="behavior sensing")
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    _login(client)
    rv = client.get(f"/admin/items/{item_id}/edit")
    assert rv.status_code == 200
    assert b"Generate Idea suggestions" in rv.data
