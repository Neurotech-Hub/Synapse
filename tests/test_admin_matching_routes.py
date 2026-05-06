"""Admin matching route tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.models import CollaborationHypothesis, FundingOpportunity, Idea, LLMRun, MatchEdge

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


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client):
    client.post(
        "/admin/login",
        data={"password": "test-pass", "submit": "Sign in"},
        follow_redirects=True,
    )


def test_admin_can_generate_review_and_create_hypothesis(app, client):
    with app.app_context():
        funding = FundingOpportunity(
            slug="funding",
            title="Behavior Pilot Funding",
            status="active",
            effort_index="moderate",
            topic_tags_json=["behavior"],
            method_tags_json=["embedded sensing"],
        )
        idea = Idea(
            slug="behavior_sensing",
            title="Behavior Sensing",
            status="public",
            tags_json=["behavior", "embedded sensing"],
        )
        db.session.add_all([funding, idea])
        db.session.commit()
        funding_id = funding.id

    _login(client)
    generated = client.post(f"/admin/matching/generate/funding/{funding_id}", follow_redirects=True)
    assert generated.status_code == 200
    assert b"Behavior Sensing" in generated.data

    with app.app_context():
        edge = MatchEdge.query.one()
        edge_id = edge.id
        assert edge.status == "needs_review"

    accepted = client.post(f"/admin/matching/edges/{edge_id}/accept", follow_redirects=True)
    assert accepted.status_code == 200
    with app.app_context():
        assert db.session.get(MatchEdge, edge_id).status == "accepted"

    created = client.post(f"/admin/matching/edges/{edge_id}/hypothesis", follow_redirects=True)
    assert created.status_code == 200
    assert b"Collaboration hypothesis" in created.data or b"Hypothesis summary" in created.data
    with app.app_context():
        assert CollaborationHypothesis.query.count() == 1


def test_admin_matching_dashboard_filters_status(app, client):
    with app.app_context():
        db.session.add_all(
            [
                MatchEdge(
                    source_type="funding",
                    source_id=1,
                    target_type="idea",
                    target_id=1,
                    match_type="funding_to_idea",
                    status="accepted",
                    score_total=0.8,
                ),
                MatchEdge(
                    source_type="funding",
                    source_id=2,
                    target_type="idea",
                    target_id=2,
                    match_type="funding_to_idea",
                    status="rejected",
                    score_total=0.2,
                ),
            ]
        )
        db.session.commit()

    _login(client)
    rv = client.get("/admin/matching?status=accepted")
    assert rv.status_code == 200
    assert b"accepted" in rv.data
    assert b"Funding #2" not in rv.data


def test_admin_match_detail_note_visibility_and_rationale(app, client):
    with app.app_context():
        edge = MatchEdge(
            source_type="funding",
            source_id=1,
            target_type="idea",
            target_id=1,
            match_type="funding_to_idea",
            status="needs_review",
            visibility="private",
            score_total=0.5,
        )
        db.session.add(edge)
        db.session.commit()
        edge_id = edge.id

    _login(client)
    rv = client.get(f"/admin/matching/edges/{edge_id}")
    assert rv.status_code == 200
    assert b"Match edge" in rv.data

    note = client.post(
        f"/admin/matching/edges/{edge_id}/note",
        data={"private_rationale": "Private note", "public_rationale": "Public candidate"},
        follow_redirects=True,
    )
    assert note.status_code == 200
    with app.app_context():
        saved = db.session.get(MatchEdge, edge_id)
        assert saved.private_rationale == "Private note"
        assert saved.public_rationale == "Public candidate"

    accept = client.post(f"/admin/matching/edges/{edge_id}/accept", follow_redirects=True)
    assert accept.status_code == 200
    public_safe = client.post(f"/admin/matching/edges/{edge_id}/public_safe", follow_redirects=True)
    assert public_safe.status_code == 200
    with app.app_context():
        saved = db.session.get(MatchEdge, edge_id)
        assert saved.status == "accepted"
        assert saved.visibility == "public_safe"


def test_admin_generate_match_rationale_logs_llmrun(app, client):
    with app.app_context():
        edge = MatchEdge(
            source_type="funding",
            source_id=1,
            target_type="idea",
            target_id=1,
            match_type="funding_to_idea",
        )
        db.session.add(edge)
        db.session.commit()
        edge_id = edge.id

    _login(client)

    def fake_generate(edge, **kwargs):
        with app.app_context():
            edge.private_rationale = "Generated rationale"
            edge.synthesized_json = {"llm_run_id": 1}
            db.session.add(
                LLMRun(
                    id=1,
                    prompt_name="match_entity_to_idea",
                    prompt_version="1.0.0",
                    provider="mock",
                    input_fingerprint="x",
                    rendered_prompt_hash="y",
                    status="ok",
                    source_type="match_edge",
                    source_id=edge.id,
                )
            )
            db.session.commit()

        class Result:
            ok = True
            errors = []

        return Result()

    from unittest.mock import patch

    with patch("app.web.admin.routes.generate_match_rationale", side_effect=fake_generate):
        rv = client.post(f"/admin/matching/edges/{edge_id}/generate-rationale", follow_redirects=True)
    assert rv.status_code == 200
    with app.app_context():
        assert LLMRun.query.filter_by(source_type="match_edge", source_id=edge_id).count() == 1
