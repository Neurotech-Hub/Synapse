"""Funding CSV validation, import, and admin upload tests."""

import os
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from app import create_app
from app.extensions import db
from app.funding.csv_import import parse_funding_csv
from app.models import FundingOpportunity

pytestmark = pytest.mark.usefixtures("_admin_env")

FIXTURE_DIR = Path(__file__).parent / "fixtures"


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


def test_funding_csv_dry_run_reports_duplicate_without_writing(app):
    payload = (FIXTURE_DIR / "funding_opportunities_sample.csv").read_text()
    with app.app_context():
        summary = parse_funding_csv(payload, commit=False)

        assert summary.total_rows == 10
        assert summary.valid_rows == 9
        assert summary.error_count == 1
        assert FundingOpportunity.query.count() == 0
        assert any("Duplicate source_url in CSV" in " ".join(row.errors) for row in summary.results)


def test_funding_csv_commit_imports_valid_rows_and_skips_invalid(app):
    payload = (FIXTURE_DIR / "funding_opportunities_sample.csv").read_text()
    with app.app_context():
        summary = parse_funding_csv(payload, commit=True)

        assert summary.created_count == 9
        assert summary.error_count == 1
        assert FundingOpportunity.query.count() == 9
        row = FundingOpportunity.query.filter_by(external_id="SYN-FUND-001").one()
        assert row.normalized_source_url == "https://example.org/funding/neurotech-seed-pilot"
        assert row.is_public is True
        assert row.topic_tags_json == ["neurotechnology", "pilot", "tool development"]
        assert row.effort_index == "mild"
        assert row.effort_score == 0.20
        assert row.effort_confidence == 1.0
        assert row.effort_signals_json == ["csv effort_index_override"]


def test_funding_csv_invalid_fixture_reports_row_errors(app):
    payload = (FIXTURE_DIR / "funding_opportunities_invalid.csv").read_text()
    with app.app_context():
        summary = parse_funding_csv(payload, commit=False)

        assert summary.valid_rows == 0
        assert summary.error_count >= 3
        messages = "\n".join("\n".join(row.errors) for row in summary.results)
        assert "Missing required title" in messages
        assert "Invalid source_url" in messages
        assert "Invalid effort_index_override" in messages


def test_funding_csv_update_existing_requires_explicit_choice(app):
    payload = """external_id,title,sponsor_name,source_url,source_type,status,visibility,deadline_date,deadline_text,amount_min,amount_max,amount_text,mechanism,effort_index_override,topic_tags,method_tags,eligibility_summary,notes_private,raw_text
SYN-FUND-001,Updated Title,Example Sponsor,https://example.org/funding/one,csv,active,public,,,,,Amount text,seed,mild,neurotechnology,,Eligibility,Notes,Raw
"""
    with app.app_context():
        db.session.add(
            FundingOpportunity(
                slug="existing",
                external_id="SYN-FUND-001",
                title="Existing Title",
                source_url="https://example.org/funding/one",
                normalized_source_url="https://example.org/funding/one",
            )
        )
        db.session.commit()

        blocked = parse_funding_csv(payload, commit=True)
        assert blocked.created_count == 0
        assert blocked.updated_count == 0
        assert blocked.error_count == 1
        assert FundingOpportunity.query.filter_by(external_id="SYN-FUND-001").one().title == "Existing Title"

        allowed = parse_funding_csv(payload, commit=True, update_existing=True)
        assert allowed.updated_count == 1
        assert FundingOpportunity.query.filter_by(external_id="SYN-FUND-001").one().title == "Updated Title"


def test_admin_can_create_edit_archive_and_import_funding(app, client):
    _login(client)

    created = client.post(
        "/admin/funding/new",
        data={
            "title": "Manual Funding",
            "external_id": "MANUAL-1",
            "source_url": "https://example.org/funding/manual",
            "source_type": "manual",
            "status": "active",
            "effort_index": "moderate",
            "topic_tags": "neurotechnology; pilot",
            "submit": "Save",
        },
        follow_redirects=True,
    )
    assert created.status_code == 200
    assert b"Manual Funding" in created.data

    with app.app_context():
        funding = FundingOpportunity.query.filter_by(external_id="MANUAL-1").one()
        funding_id = funding.id
        assert funding.topic_tags_json == ["neurotechnology", "pilot"]

    edited = client.post(
        f"/admin/funding/{funding_id}/edit",
        data={
            "title": "Manual Funding Edited",
            "external_id": "MANUAL-1",
            "source_url": "https://example.org/funding/manual",
            "source_type": "manual",
            "status": "active",
            "effort_index": "heavy",
            "is_reviewed": "y",
            "submit": "Save",
        },
        follow_redirects=True,
    )
    assert edited.status_code == 200
    assert b"Manual Funding Edited" in edited.data

    archived = client.post(f"/admin/funding/{funding_id}/archive", follow_redirects=True)
    assert archived.status_code == 200
    with app.app_context():
        assert db.session.get(FundingOpportunity, funding_id).status == "archived"

    upload_payload = b"""external_id,title,sponsor_name,source_url,source_type,status,visibility,deadline_date,deadline_text,amount_min,amount_max,amount_text,mechanism,effort_index_override,topic_tags,method_tags,eligibility_summary,notes_private,raw_text
UPLOAD-1,Uploaded Funding,Example Sponsor,https://example.org/funding/uploaded,csv,active,public,2026-07-01,July 1 2026,1000,2000,"$2,000",seed,mild,neurotechnology,,Eligibility,Notes,Raw
"""
    imported = client.post(
        "/admin/funding/import",
        data={"csv_file": (BytesIO(upload_payload), "funding.csv"), "commit": "y", "submit": "Validate CSV"},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert imported.status_code == 200
    with app.app_context():
        assert FundingOpportunity.query.filter_by(external_id="UPLOAD-1").one().title == "Uploaded Funding"


def test_admin_can_fetch_funding_source_text(app, client):
    with app.app_context():
        funding = FundingOpportunity(
            slug="fetch_me",
            title="Fetch Me",
            source_url="https://example.org/funding/fetch-me",
        )
        db.session.add(funding)
        db.session.commit()
        funding_id = funding.id

    class _PageText:
        title = "Fetched title"
        text = "Fetched source text for a seed grant."
        content_hash = "a" * 64

    class _Result:
        ok = True
        final_url = "https://example.org/funding/fetch-me"
        status_code = 200
        content_type = "text/html"
        error = None
        page_text = _PageText()
        fetched_at = None

    _login(client)
    with patch("app.web.admin.routes.fetch_funding_page_text", return_value=_Result()):
        rv = client.post(f"/admin/funding/{funding_id}/fetch-source", follow_redirects=True)

    assert rv.status_code == 200
    with app.app_context():
        saved = db.session.get(FundingOpportunity, funding_id)
        assert saved.raw_text == "Fetched source text for a seed grant."
        assert saved.raw_text_hash == "a" * 64
        assert saved.source_text_chars == len("Fetched source text for a seed grant.")
        assert saved.synthesis_status == "fetched"


def test_admin_can_clear_fetch_error(app, client):
    with app.app_context():
        funding = FundingOpportunity(
            slug="fetch_error",
            title="Fetch Error",
            source_url="https://example.org/funding/error",
            fetch_error="timeout",
        )
        db.session.add(funding)
        db.session.commit()
        funding_id = funding.id

    _login(client)
    rv = client.post(f"/admin/funding/{funding_id}/clear-fetch-error", follow_redirects=True)
    assert rv.status_code == 200
    with app.app_context():
        assert db.session.get(FundingOpportunity, funding_id).fetch_error is None
