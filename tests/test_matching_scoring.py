"""Deterministic matching service tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.matching.service import create_hypothesis_from_match, generate_funding_to_idea_matches, score_funding_to_idea
from app.models import CollaborationHypothesis, FundingOpportunity, Idea, MatchEdge

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


def test_funding_to_idea_score_uses_tag_overlap(app):
    funding = FundingOpportunity(
        slug="funding",
        title="Behavioral Systems Pilot",
        status="active",
        effort_index="moderate",
        topic_tags_json=["behavior", "pilot"],
        method_tags_json=["embedded sensing"],
        mechanism="seed grant",
    )
    idea = Idea(
        slug="idea",
        title="Embedded Behavioral Sensing",
        tags_json=["behavior", "embedded sensing"],
        aliases_json=["home cage behavior"],
    )

    candidate = score_funding_to_idea(funding, idea)

    assert candidate.score_total >= 0.35
    assert "behavior" in candidate.features["shared_terms"]
    assert candidate.evidence
    assert "Effort is tracked separately" in candidate.rationale


def test_generate_funding_to_idea_matches_creates_edges(app):
    with app.app_context():
        funding = FundingOpportunity(
            slug="funding",
            title="Neurotech Pilot",
            status="active",
            effort_index="mild",
            topic_tags_json=["neurotechnology", "pilot"],
            method_tags_json=["data logging"],
        )
        idea_match = Idea(
            slug="data_logging",
            title="Data logging",
            tags_json=["neurotechnology", "data logging"],
            status="public",
        )
        idea_skip = Idea(slug="unrelated", title="Unrelated", tags_json=["immunology"])
        db.session.add_all([funding, idea_match, idea_skip])
        db.session.commit()

        run = generate_funding_to_idea_matches(funding, candidate_limit=10, min_score=0.35)

        assert run.status == "ok"
        assert run.scored_count == 1
        edge = MatchEdge.query.filter_by(match_type="funding_to_idea").one()
        assert edge.source_id == funding.id
        assert edge.target_id == idea_match.id
        assert edge.status == "needs_review"
        assert edge.visibility == "private"


def test_create_hypothesis_from_match(app):
    with app.app_context():
        funding = FundingOpportunity(slug="funding", title="Pilot Funding", status="active", effort_index="moderate")
        idea = Idea(slug="idea", title="Behavior Platform")
        db.session.add_all([funding, idea])
        db.session.flush()
        edge = MatchEdge(
            source_type="funding",
            source_id=funding.id,
            target_type="idea",
            target_id=idea.id,
            match_type="funding_to_idea",
            score_total=0.8,
            score_funding_fit=0.75,
            score_effort_reasonableness=0.8,
            score_evidence_strength=0.7,
            score_strategic_value=0.55,
            rationale="Shared behavior terms.",
            evidence_json=[{"kind": "funding_summary"}],
            features_json={"shared_terms": ["behavior"]},
        )
        db.session.add(edge)
        db.session.commit()

        hyp = create_hypothesis_from_match(edge)

        assert hyp.status == "needs_review"
        assert hyp.priority == "high"
        assert hyp.idea_id == idea.id
        assert hyp.funding_opportunity_id == funding.id
        assert CollaborationHypothesis.query.count() == 1
