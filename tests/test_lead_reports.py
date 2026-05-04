"""Hub-centric lead reports (admin CRUD + review hooks)."""

import os
from unittest.mock import patch

import pytest

from app import create_app
from app.extensions import db
from app.leads.stuck_reports import reconcile_interrupted_lead_reports
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
        o = Organization(slug="huborg", display_name="Hub Org", notes=None, is_hub=True)
        p = Person(slug="subj_one", display_name="Subject Person", notes=None)
        db.session.add_all([o, p])
        db.session.commit()
        oid, pid = o.id, p.id

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
        rep.status = "ok"
        db.session.commit()
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


def test_reconcile_marks_stuck_running_as_failed(app):
    with app.app_context():
        p = Person(slug="stuck_subj", display_name="Stuck Subject", notes=None)
        db.session.add(p)
        db.session.flush()
        lr = LeadReport(
            target_person_id=int(p.id),
            status="running",
            hub_organization_id=None,
        )
        db.session.add(lr)
        db.session.commit()
        rid = int(lr.id)

        assert reconcile_interrupted_lead_reports() == 1
        row = db.session.get(LeadReport, rid)
        assert row is not None
        assert row.status == "failed"
        assert "Interrupted" in (row.error_detail or "")
        assert row.completed_at is not None

        assert reconcile_interrupted_lead_reports() == 0


def test_people_roster_excludes_hub_org_members(app):
    from app.leads.report_pipeline import _people_roster_for_orgs

    with app.app_context():
        hub = Organization(slug="thehub", display_name="The Hub", notes=None)
        target = Organization(slug="targetlab", display_name="Target Lab", notes=None)
        p_hub = Person(slug="hub_member", display_name="Hub Member", notes=None)
        p_lab_only = Person(slug="lab_only", display_name="Lab Only", notes=None)
        db.session.add_all([hub, target, p_hub, p_lab_only])
        db.session.flush()
        hub.people.append(p_hub)
        target.people.append(p_hub)
        target.people.append(p_lab_only)
        db.session.commit()

        people, _roster = _people_roster_for_orgs([int(target.id)], hub_organization_id=int(hub.id))
        ids = {p.id for p in people}
        assert int(p_lab_only.id) in ids
        assert int(p_hub.id) not in ids

        people2, _ = _people_roster_for_orgs([int(target.id)], hub_organization_id=None)
        assert int(p_hub.id) in {p.id for p in people2}


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
