"""Force HTML content item refresh (UPSERT by sha256) — bypasses poll snapshot dedupe."""

import hashlib
from unittest.mock import patch

import pytest

from app import create_app
from app.extensions import db
from app.ingest.html_extract import html_poll_content_external_id
from app.ingest.pipeline import refresh_html_page_content_item
from app.models import ContentItem, Source

pytestmark = pytest.mark.usefixtures("_admin_env")


@pytest.fixture(scope="module", autouse=True)
def _admin_env():
    import os

    os.environ["ADMIN_PASSWORD"] = "test-pass"
    yield


def _html_body() -> bytes:
    return (
        b"<!DOCTYPE html><html><head><title>Persist Title</title></head>"
        b"<body><p>ALPHA_UNIQUE_SNIPPET_TOKEN beta.</p></body></html>"
    )


@pytest.fixture()
def app(tmp_path):
    db_file = tmp_path / "refresh.db"
    flask_app = create_app(
        override_config={
            "TESTING": True,
            "DEBUG": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
            "WTF_CSRF_ENABLED": False,
            "SYNAPSE_HTML_PAGE_LLM": False,
            "SYNAPSE_LEADS_INGEST": False,
        },
    )
    with flask_app.app_context():
        db.create_all()
        yield flask_app


def test_refresh_html_page_updates_snippet_when_hash_unchanged(app):
    body = _html_body()
    h = hashlib.sha256(body).hexdigest()
    ext_id = html_poll_content_external_id(body)

    with app.app_context():
        src = Source(
            url="https://example.invalid/page",
            kind="html_page",
            enabled=True,
            pending=False,
        )
        db.session.add(src)
        db.session.flush()
        db.session.add(
            ContentItem(
                source_id=src.id,
                external_id=ext_id,
                title="Old title",
                link=src.url,
                snippet="stale snippet should be replaced",
            )
        )
        db.session.commit()
        sid = src.id
        ci_id = ContentItem.query.filter_by(source_id=sid, external_id=ext_id).first().id

    with app.app_context(), patch("app.ingest.pipeline._fetch_source_url_body", return_value=body):
        src2 = db.session.get(Source, sid)
        out = refresh_html_page_content_item(src2, commit=True)
        assert out["status"] == "updated"
        assert out["external_id"] == ext_id
        assert out["content_item_id"] == ci_id

    with app.app_context():
        ci = db.session.get(ContentItem, ci_id)
        assert ci is not None
        assert "ALPHA_UNIQUE_SNIPPET_TOKEN" in (ci.snippet or "")
        assert ci.title == "Persist Title"


def test_refresh_html_page_creates_content_item_when_missing(app):
    body = _html_body()
    h = hashlib.sha256(body).hexdigest()
    ext_id = html_poll_content_external_id(body)

    with app.app_context():
        src = Source(
            url="https://example.invalid/new-page",
            kind="html_page",
            enabled=True,
            pending=False,
        )
        db.session.add(src)
        db.session.commit()
        sid = src.id

    with app.app_context(), patch("app.ingest.pipeline._fetch_source_url_body", return_value=body):
        src2 = db.session.get(Source, sid)
        out = refresh_html_page_content_item(src2, commit=True)
        assert out["status"] == "created"
        assert out["external_id"] == ext_id

    with app.app_context():
        ci = ContentItem.query.filter_by(source_id=sid, external_id=ext_id).first()
        assert ci is not None
        assert "ALPHA_UNIQUE_SNIPPET_TOKEN" in (ci.snippet or "")


def test_refresh_html_page_skipped_for_rss_kind(app):
    with app.app_context():
        src = Source(
            url="https://example.invalid/feed.xml",
            kind="rss_feed",
            enabled=True,
            pending=False,
        )
        db.session.add(src)
        db.session.commit()
        sid = src.id

    with app.app_context():
        src2 = db.session.get(Source, sid)
        out = refresh_html_page_content_item(src2, commit=True)
        assert out["status"] == "skipped"
        assert "html_page" in (out.get("detail") or "")


def test_refresh_html_page_uses_llm_when_enabled(app):
    body = _html_body()
    h = hashlib.sha256(body).hexdigest()
    ext_id = html_poll_content_external_id(body)

    app2 = create_app(
        override_config={
            "TESTING": True,
            "DEBUG": False,
            "SQLALCHEMY_DATABASE_URI": app.config["SQLALCHEMY_DATABASE_URI"],
            "WTF_CSRF_ENABLED": False,
            "SYNAPSE_HTML_PAGE_LLM": True,
            "SYNAPSE_LEADS_INGEST": False,
        },
    )

    with app2.app_context():
        src = Source(
            url="https://example.invalid/llm-page",
            kind="html_page",
            enabled=True,
            pending=False,
        )
        db.session.add(src)
        db.session.flush()
        db.session.add(
            ContentItem(
                source_id=src.id,
                external_id=ext_id,
                title="Old",
                link=src.url,
                snippet="stale",
            )
        )
        db.session.commit()
        sid = src.id
        ci_id = ContentItem.query.filter_by(source_id=sid, external_id=ext_id).first().id

    mock_sum = {"title": "LLM Title", "snippet": "DETAIL_FROM_SUMMARIZER long enough to assert."}

    with app2.app_context(), patch("app.ingest.pipeline._fetch_source_url_body", return_value=body), patch(
        "app.ingest.pipeline.try_summarize_html_page", return_value=mock_sum
    ):
        src2 = db.session.get(Source, sid)
        out = refresh_html_page_content_item(src2, commit=True)
        assert out["status"] == "updated"

    with app2.app_context():
        ci = db.session.get(ContentItem, ci_id)
        assert ci.title == "LLM Title"
        assert "DETAIL_FROM_SUMMARIZER" in (ci.snippet or "")
