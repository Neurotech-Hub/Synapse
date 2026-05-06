"""Funding opportunity model tests."""

import os

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
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


def test_funding_opportunity_allows_sparse_record(app):
    with app.app_context():
        row = FundingOpportunity(slug="sparse_seed", title="Sparse Seed")
        db.session.add(row)
        db.session.commit()

        saved = FundingOpportunity.query.filter_by(slug="sparse_seed").one()
        assert saved.title == "Sparse Seed"
        assert saved.status == "draft"
        assert saved.source_type == "manual"
        assert saved.effort_index == "unknown"
        assert saved.is_public is False
        assert saved.topic_tags_json == []


def test_funding_opportunity_rejects_invalid_effort(app):
    with app.app_context():
        row = FundingOpportunity(slug="bad_effort", title="Bad Effort", effort_index="none")
        db.session.add(row)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_public_visibility_is_independent_of_status(app):
    with app.app_context():
        row = FundingOpportunity(
            slug="public_draft",
            title="Public Draft",
            status="draft",
            is_public=True,
            is_reviewed=True,
        )
        db.session.add(row)
        db.session.commit()

        saved = FundingOpportunity.query.filter_by(slug="public_draft").one()
        assert saved.status == "draft"
        assert saved.is_public is True
        assert saved.is_reviewed is True
