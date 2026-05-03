"""HTML page ingestion: snapshots + ContentItem rows."""

from unittest.mock import patch

import pytest

from app import create_app
from app.extensions import db
from app.ingest.pipeline import run_poll
from app.models import ContentItem, Source, SourceSnapshot

pytestmark = pytest.mark.usefixtures("_admin_env")


@pytest.fixture(scope="module", autouse=True)
def _admin_env():
    import os

    os.environ["ADMIN_PASSWORD"] = "test-pass"
    yield


class _BytesResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


@pytest.fixture()
def app(tmp_path):
    db_file = tmp_path / "test.db"
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


def test_html_page_poll_creates_snapshot_and_content_item(app):
    html = (
        b"<!DOCTYPE html><html><head><title>T Lab Page</title></head>"
        b"<body><p>Quarterly roadmap update beta.</p>"
        b"<script>ignored()</script></body></html>"
    )

    with app.app_context():
        db.session.add(
            Source(
                url="https://example.invalid/lab-news",
                kind="html_page",
                enabled=True,
                pending=False,
            )
        )
        db.session.commit()

    with app.app_context(), patch(
        "app.ingest.pipeline.urllib.request.urlopen",
        return_value=_BytesResponse(html),
    ):
        log = run_poll()
        assert log.ok is True

    with app.app_context():
        s = Source.query.filter_by(url="https://example.invalid/lab-news").first()
        assert s is not None
        snaps = SourceSnapshot.query.filter_by(source_id=s.id).all()
        assert len(snaps) == 1
        items = ContentItem.query.filter_by(source_id=s.id).all()
        assert len(items) == 1
        it = items[0]
        assert it.external_id.startswith("sha256:")
        assert "Lab Page" in (it.title or "")
        assert "roadmap" in (it.snippet or "").lower()
        assert it.link == "https://example.invalid/lab-news"


def test_html_page_duplicate_hash_no_second_content(app):
    html = b"<html><head><title>Same</title></head><body><p>Stable body.</p></body></html>"

    with app.app_context():
        db.session.add(
            Source(
                url="https://example.invalid/static",
                kind="html_page",
                enabled=True,
                pending=False,
            )
        )
        db.session.commit()

    mock_open = patch(
        "app.ingest.pipeline.urllib.request.urlopen",
        return_value=_BytesResponse(html),
    )
    with app.app_context(), mock_open:
        run_poll()
        run_poll()

    with app.app_context():
        s = Source.query.filter_by(url="https://example.invalid/static").first()
        assert SourceSnapshot.query.filter_by(source_id=s.id).count() == 1
        assert ContentItem.query.filter_by(source_id=s.id).count() == 1
