"""Hub-centric lead reports (admin CRUD + review hooks)."""

import os
from unittest.mock import patch

import pytest

from app import create_app
from app.extensions import db
from app.leads.pipeline_settings import get_singleton
from app.models import LeadReport, Organization, Person

pytestmark = pytest.mark.usefixtures("_admin_env")


@pytest.fixture(scope="module", autouse=True)
def _admin_env():
    os.environ["ADMIN_PASSWORD"] = "test-pass"
    yield


@pytest.fixture()
def app(tmp_path):
    db_file = tmp_path / "lr.db"
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


def test_lead_report_new_get_redirects_to_leads_modal(client):
    _login(client)
    r = client.get("/admin/leads/reports/new", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers.get("Location") or ""
    assert "/admin/leads" in loc
    assert "open_report_modal=1" in loc


def test_lead_report_enqueue_without_background_runner(app, client):
    with app.app_context():
        o = Organization(slug="huborg", display_name="Hub Org", notes=None)
        p = Person(slug="subj_one", display_name="Subject Person", notes=None)
        db.session.add_all([o, p])
        db.session.commit()
        oid, pid = o.id, p.id
        row = get_singleton()
        row.hub_organization_id = oid
        db.session.commit()

    _login(client)
    with patch("app.web.admin.routes.start_background_lead_report", return_value=(True, "")):
        r = client.post(
            "/admin/leads/reports/new",
            data={"subject_kind": "person", "target_person_id": str(pid)},
            follow_redirects=True,
        )
    assert r.status_code == 200
    with app.app_context():
        rep = LeadReport.query.filter_by(target_person_id=pid).first()
        assert rep is not None
        assert rep.status == "queued"
        rid = rep.id

    r2 = client.post(
        f"/admin/leads/reports/{rid}/review",
        data={"review_notes": "Looks good"},
        follow_redirects=True,
    )
    assert r2.status_code == 200
    with app.app_context():
        rep2 = db.session.get(LeadReport, rid)
        assert rep2.reviewed_at is not None
        assert rep2.review_notes == "Looks good"


def test_person_delete_blocked_by_lead_report(app, client):
    with app.app_context():
        p = Person(slug="blockme", display_name="Block Delete", notes=None)
        db.session.add(p)
        db.session.flush()
        db.session.add(LeadReport(target_person_id=p.id, status="ok", hub_organization_id=None))
        db.session.commit()
        pid = p.id

    _login(client)
    r = client.post(f"/admin/people/{pid}/delete", follow_redirects=True)
    assert r.status_code == 200
    assert b"Delete lead reports" in r.data
    with app.app_context():
        assert db.session.get(Person, pid) is not None
