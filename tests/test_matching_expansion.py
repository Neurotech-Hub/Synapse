"""Expanded deterministic matching tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.matching.service import create_hypothesis_for_target, create_manual_match_edge, generate_match_rationale, generate_person_to_idea_matches
from app.models import CollaborationHypothesis, Idea, LLMRun, MatchEdge, Person, PersonaSnapshot

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


def test_person_to_idea_matching_and_target_hypothesis(app):
    with app.app_context():
        person = Person(slug="pi", display_name="PI")
        idea = Idea(slug="behavior", title="Behavior Sensing", tags_json=["behavior", "embedded sensing"])
        db.session.add_all([person, idea])
        db.session.flush()
        db.session.add(PersonaSnapshot(person_id=person.id, research_focus=["behavior"], methods=["embedded sensing"]))
        db.session.commit()

        run = generate_person_to_idea_matches(person)
        assert run.scored_count == 1
        edge = MatchEdge.query.one()
        edge.status = "accepted"
        db.session.commit()

        hyp = create_hypothesis_for_target("person", person.id)
        assert hyp.status == "needs_review"
        assert CollaborationHypothesis.query.count() == 1


def test_manual_match_edge(app):
    with app.app_context():
        edge = create_manual_match_edge(
            source_type="idea",
            source_id=1,
            target_type="funding",
            target_id=2,
            match_type="idea_to_funding",
            visibility="public_safe",
        )
        assert edge.status == "accepted"
        assert edge.visibility == "public_safe"


def test_generate_match_rationale_with_mock_provider(app):
    with app.app_context():
        edge = MatchEdge(
            source_type="person",
            source_id=1,
            target_type="idea",
            target_id=2,
            match_type="person_to_idea",
            score_total=0.5,
            features_json={"shared_terms": ["behavior"]},
        )
        db.session.add(edge)
        db.session.commit()

        result = generate_match_rationale(
            edge,
            provider="mock",
            mock_provider=lambda prompt, model: (
                '{"schema_version":"1.0","match_score":0.7,"relationship_type":"direct",'
                '"rationale":"Strong behavior overlap.","supporting_points":["behavior"],"confidence":0.8,"warnings":[]}'
            ),
        )

        assert result.ok
        assert edge.private_rationale == "Strong behavior overlap."
        assert edge.public_rationale
        assert edge.synthesized_json["llm_run_id"] == LLMRun.query.one().id
