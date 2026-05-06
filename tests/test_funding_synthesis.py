"""Funding synthesis draft workflow tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.funding.synthesis import (
    apply_funding_public_card,
    apply_funding_synthesis_draft,
    regenerate_funding_public_card,
    reclassify_effort_from_synthesis,
    synthesize_funding_from_raw_text,
)
from app.funding.synthesis_review import apply_funding_synthesis_fields, get_funding_synthesis_diff
from app.models import FundingOpportunity, LLMRun

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
                '"effort_label":"mild","confidence":0.9,"best_for":[],"tags":["pilot"],"warnings":[]}'
            ),
        )

        assert result.ok
        assert funding.summary_public == "Reviewed public summary"
        assert funding.synthesized_json["public_card"]["short_summary"] == "Draft public card"

        changed = apply_funding_public_card(funding)
        assert "summary_public" in changed
        assert funding.summary_public == "Draft public card"
        assert funding.topic_tags_json == ["pilot"]


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
