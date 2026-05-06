"""Match and collaboration hypothesis model tests."""

import os

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import CollaborationHypothesis, MatchEdge, MatchRun

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


def test_match_edge_and_run_store_scores(app):
    with app.app_context():
        run = MatchRun(run_type="funding_to_idea", status="ok", candidates_count=1, scored_count=1)
        db.session.add(run)
        db.session.flush()
        edge = MatchEdge(
            match_run_id=run.id,
            source_type="funding",
            source_id=1,
            target_type="idea",
            target_id=2,
            match_type="funding_to_idea",
            score_total=0.72,
            confidence=0.66,
            rationale="Shared tags.",
            evidence_json=[{"kind": "manual_note"}],
            features_json={"shared_tags": ["behavior"]},
        )
        db.session.add(edge)
        db.session.commit()

        saved = MatchEdge.query.one()
        assert saved.run.id == run.id
        assert saved.status == "needs_review"
        assert saved.visibility == "private"
        assert saved.features_json["shared_tags"] == ["behavior"]


def test_match_edge_rejects_invalid_status(app):
    with app.app_context():
        edge = MatchEdge(
            source_type="funding",
            source_id=1,
            target_type="idea",
            target_id=2,
            match_type="funding_to_idea",
            status="approved",
        )
        db.session.add(edge)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_collaboration_hypothesis_private_defaults(app):
    with app.app_context():
        hyp = CollaborationHypothesis(title="Hypothesis", target_type="idea", target_id=1)
        db.session.add(hyp)
        db.session.commit()

        saved = CollaborationHypothesis.query.one()
        assert saved.status == "draft"
        assert saved.priority == "normal"
        assert saved.related_match_edge_ids_json == []
