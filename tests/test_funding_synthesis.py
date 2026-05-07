"""Funding synthesis draft workflow tests."""

import os
from unittest.mock import patch

import pytest

from app import create_app
from app.extensions import db
from app.funding.extract import FundingPageText
from app.funding.fetch import FundingFetchResult
from app.funding.synthesis import (
    apply_funding_public_card,
    apply_funding_synthesis_draft,
    generate_public_ready_funding_card,
    regenerate_funding_public_card,
    reclassify_effort_from_synthesis,
    synthesize_funding_from_raw_text,
)
from app.funding.synthesis_review import apply_funding_synthesis_fields, get_funding_synthesis_diff
from app.models import FundingOpportunity, LLMRun
from app.llm.providers import ProviderResult

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


def test_funding_synthesis_creates_review_draft(app):
    with app.app_context():
        funding = FundingOpportunity(slug="seed", title="Original", source_url="https://example.org", raw_text="seed grant")
        db.session.add(funding)
        db.session.commit()

        result = synthesize_funding_from_raw_text(
            funding,
            provider="mock",
            mock_provider=lambda prompt, model: (
                '{"schema_version":"1.0","title":"Synthetic Seed Grant","public_summary":"Public summary",'
                '"topic_tags":["neurotechnology"],"method_tags":["embedded"],"confidence":0.8,'
                '"missing_information":[],"warnings":[]}'
            ),
        )

        assert result.ok
        assert funding.synthesis_status == "needs_review"
        assert funding.synthesized_json["title"] == "Synthetic Seed Grant"
        assert LLMRun.query.count() == 1

        changed = apply_funding_synthesis_draft(funding)
        assert "title" in changed
        assert funding.title == "Synthetic Seed Grant"
        assert funding.topic_tags_json == ["neurotechnology"]


def test_funding_synthesis_diff_and_selected_apply_preserves_manual_values(app):
    with app.app_context():
        funding = FundingOpportunity(
            slug="selective",
            title="Manual Title",
            sponsor_name="Manual Sponsor",
            summary_public="Manual summary",
            synthesized_json={
                "title": "Draft Title",
                "sponsor_name": "Manual Sponsor",
                "public_summary": "Draft summary",
                "topic_tags": ["neurotech", "neurotech", " behavior "],
                "deadline_date": "2026-07-01",
            },
        )
        db.session.add(funding)
        db.session.commit()

        diffs = {row.field: row for row in get_funding_synthesis_diff(funding)}
        assert diffs["title"].status == "changed"
        assert diffs["sponsor_name"].status == "unchanged"
        assert diffs["topic_tags_json"].status == "new"
        assert diffs["deadline_date"].status == "new"
        assert diffs["title"].is_manual is True

        changed = apply_funding_synthesis_fields(funding, ["summary_public", "topic_tags_json", "deadline_date"])
        assert set(changed) == {"summary_public", "topic_tags_json", "deadline_date"}
        assert funding.title == "Manual Title"
        assert funding.sponsor_name == "Manual Sponsor"
        assert funding.summary_public == "Draft summary"
        assert funding.topic_tags_json == ["neurotech", "behavior"]
        assert str(funding.deadline_date) == "2026-07-01"


def test_public_card_regeneration_is_review_gated(app):
    with app.app_context():
        funding = FundingOpportunity(
            slug="card",
            title="Card Source",
            summary_public="Reviewed public summary",
            effort_index="mild",
        )
        db.session.add(funding)
        db.session.commit()

        result = regenerate_funding_public_card(
            funding,
            provider="mock",
            mock_provider=lambda prompt, model: (
                '{"schema_version":"1.0","display_title":"Card title","short_summary":"Draft public card",'
                '"effort_label":"mild","confidence":0.9,"not_enough_information":false,'
                '"best_for":[],"tags":["pilot"],"missing_information":[],"warnings":[]}'
            ),
        )

        assert result.ok
        assert funding.summary_public == "Reviewed public summary"
        assert funding.synthesized_json["public_card"]["short_summary"] == "Draft public card"

        changed = apply_funding_public_card(funding)
        assert "summary_public" in changed
        assert funding.summary_public == "Draft public card"
        assert funding.topic_tags_json == ["pilot"]


def test_public_ready_generation_applies_and_marks_public(app):
    with app.app_context():
        funding = FundingOpportunity(
            slug="ready",
            title="Ready Source",
            sponsor_name="Example Sponsor",
            status="draft",
            amount_text="",
            deadline_text="",
        )
        db.session.add(funding)
        db.session.commit()

        result = generate_public_ready_funding_card(
            funding,
            provider="mock",
            mock_provider=lambda prompt, model: (
                '{"schema_version":"1.0","display_title":"Ready Source","short_summary":"Supports pilot neurotechnology work.",'
                '"eligibility_summary":"Faculty teams may apply.","amount_text":"Up to $100,000",'
                '"deadline_text":"Rolling","deadline_date":null,"effort_label":"mild",'
                '"effort_rationale":"Short application expected.","topic_tags":["neurotechnology"],'
                '"method_tags":["pilot"],"confidence":0.86,"not_enough_information":false,'
                '"missing_information":[],"warnings":[]}'
            ),
        )

        assert result.ok
        assert funding.synthesis_status == "synthesized"
        assert funding.is_reviewed is True
        assert funding.is_public is True
        assert funding.status == "active"
        assert funding.summary_public == "Supports pilot neurotechnology work."
        assert funding.eligibility_summary == "Faculty teams may apply."
        assert funding.amount_text == "Up to $100,000"
        assert funding.deadline_text == "Rolling"
        assert funding.effort_index == "mild"
        assert funding.effort_confidence == 0.86
        assert funding.topic_tags_json == ["neurotechnology"]
        assert funding.method_tags_json == ["pilot"]


def test_public_ready_generation_keeps_sparse_output_private(app):
    with app.app_context():
        funding = FundingOpportunity(slug="sparse", title="Sparse Source", status="draft")
        db.session.add(funding)
        db.session.commit()

        result = generate_public_ready_funding_card(
            funding,
            provider="mock",
            mock_provider=lambda prompt, model: (
                '{"schema_version":"1.0","display_title":"Sparse Source","short_summary":"",'
                '"effort_label":"unknown","confidence":0.2,"not_enough_information":true,'
                '"missing_information":["amount","deadline","eligibility"],"warnings":[]}'
            ),
        )

        assert result.ok
        assert funding.synthesis_status == "needs_review"
        assert funding.is_reviewed is False
        assert funding.is_public is False
        assert "Needs more context" in (funding.synthesis_error or "")


def test_admin_public_ready_generation_fetches_source_context(app, client):
    with app.app_context():
        funding = FundingOpportunity(
            slug="route-ready",
            title="Route Ready",
            source_url="https://example.org/funding",
            status="draft",
        )
        db.session.add(funding)
        db.session.commit()
        funding_id = funding.id

    seen_prompt = {}

    def fake_provider(provider, prompt, **kwargs):
        seen_prompt["text"] = prompt
        return ProviderResult(
            raw_text=(
                '{"schema_version":"1.0","display_title":"Route Ready","short_summary":"Public ready summary.",'
                '"eligibility_summary":"Researchers may apply.","amount_text":"Up to $50,000",'
                '"deadline_text":"June 1","deadline_date":null,"effort_label":"mild",'
                '"effort_rationale":"Short form expected.","topic_tags":["funding"],'
                '"method_tags":[],"confidence":0.8,"not_enough_information":false,'
                '"missing_information":[],"warnings":[]}'
            ),
            provider=provider,
            model_name=kwargs.get("model_name"),
        )

    fetch_result = FundingFetchResult(
        requested_url="https://example.org/funding",
        final_url="https://example.org/funding",
        status_code=200,
        content_type="text/html",
        page_text=FundingPageText(title="Funding page", text="Scraped eligibility and award details.", content_hash="abc123"),
    )

    _login(client)
    with patch("app.web.admin.routes.fetch_funding_page_text", return_value=fetch_result), patch(
        "app.llm.execute.run_prompt_provider",
        side_effect=fake_provider,
    ):
        response = client.post(f"/admin/funding/{funding_id}/generate-public-card", follow_redirects=True)

    assert response.status_code == 200
    assert "Scraped eligibility and award details." in seen_prompt["text"]
    with app.app_context():
        saved = db.session.get(FundingOpportunity, funding_id)
        assert saved is not None
        assert saved.raw_text == "Scraped eligibility and award details."
        assert saved.is_public is True
        assert saved.is_reviewed is True
        assert saved.summary_public == "Public ready summary."


def test_effort_from_synthesis_is_separate(app):
    with app.app_context():
        funding = FundingOpportunity(
            slug="effort",
            title="Effort",
            effort_index="unknown",
            synthesized_json={"effort_index": "heavy", "effort_rationale": "Center-scale", "confidence": 0.7},
        )
        db.session.add(funding)
        db.session.commit()

        reclassify_effort_from_synthesis(funding)
        assert funding.effort_index == "heavy"
        assert funding.effort_rationale == "Center-scale"
        assert funding.effort_confidence == 0.7
