"""Effort index classifier and admin action tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.funding.effort import classify_effort_heuristic
from app.models import FundingOpportunity

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


@pytest.mark.parametrize(
    ("funding", "expected"),
    [
        (FundingOpportunity(title="$5,000 Travel Award", slug="travel", amount_max=5_000, mechanism="travel award"), "mild"),
        (FundingOpportunity(title="$20,000 Seed Grant", slug="seed", amount_max=20_000, mechanism="seed grant"), "mild"),
        (
            FundingOpportunity(
                title="$100,000 Foundation Pilot",
                slug="foundation",
                amount_max=100_000,
                mechanism="foundation award",
                raw_text="brief proposal and budget justification",
            ),
            "moderate",
        ),
        (
            FundingOpportunity(
                title="$300,000 Technology Development Award",
                slug="tech",
                amount_max=300_000,
                mechanism="technology development award",
            ),
            "moderate",
        ),
        (
            FundingOpportunity(
                title="$2M Center Grant",
                slug="center",
                amount_max=2_000_000,
                mechanism="center grant",
                raw_text="requires management plan and institutional commitment",
            ),
            "heavy",
        ),
        (
            FundingOpportunity(
                title="Multi-site Consortium Call",
                slug="consortium",
                mechanism="consortium",
                raw_text="multiple institutions required and advisory board required",
            ),
            "heavy",
        ),
        (FundingOpportunity(title="Sparse Newsletter Mention", slug="sparse"), "unknown"),
    ],
)
def test_effort_heuristic_examples(funding, expected):
    classification = classify_effort_heuristic(funding)

    assert classification.effort_index == expected
    assert classification.rationale
    assert classification.signals
    if expected == "unknown":
        assert classification.effort_score is None
    else:
        assert classification.effort_score is not None
        assert classification.confidence >= 0.5


def test_admin_rebuild_effort_updates_classification(app, client):
    with app.app_context():
        funding = FundingOpportunity(
            slug="admin_effort",
            title="Strategic Center Opportunity",
            amount_max=2_500_000,
            mechanism="center grant",
            raw_text="requires multi-PI team, management plan, and institutional commitment",
            effort_index="unknown",
        )
        db.session.add(funding)
        db.session.commit()
        funding_id = funding.id

    _login(client)
    rv = client.post(f"/admin/funding/{funding_id}/effort/rebuild", follow_redirects=True)

    assert rv.status_code == 200
    assert b"heavy" in rv.data
    with app.app_context():
        saved = db.session.get(FundingOpportunity, funding_id)
        assert saved.effort_index == "heavy"
        assert saved.effort_score == 0.85
        assert saved.effort_confidence is not None
        assert saved.effort_signals_json


def test_admin_manual_override_marks_effort_reviewed(app, client):
    with app.app_context():
        funding = FundingOpportunity(slug="manual_override", title="Manual Override", effort_index="unknown")
        db.session.add(funding)
        db.session.commit()
        funding_id = funding.id

    _login(client)
    rv = client.post(
        f"/admin/funding/{funding_id}/edit",
        data={
            "title": "Manual Override",
            "source_type": "manual",
            "status": "draft",
            "effort_index": "moderate",
            "effort_rationale": "Admin reviewed the opportunity page and set a manual label.",
            "submit": "Save",
        },
        follow_redirects=True,
    )

    assert rv.status_code == 200
    with app.app_context():
        saved = db.session.get(FundingOpportunity, funding_id)
        assert saved.effort_index == "moderate"
        assert saved.effort_confidence == 1.0
        assert saved.effort_reviewed_at is not None
        assert saved.effort_signals_json == ["admin manual effort override"]
