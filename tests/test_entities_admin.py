"""People / organizations admin and XOR source ownership (no legacy Entity model)."""

import os

import pytest
from werkzeug.datastructures import MultiDict

from app import create_app
from app.domain.entity_associations import sync_person_organizations
from app.extensions import db
from app.models import Organization, Person, PersonaSnapshot, Source

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


def test_admin_source_xor_organization_roundtrip(app, client):
    with app.app_context():
        db.session.add(
            Source(url="https://example.org/track", kind="rss_feed", enabled=True, pending=False),
        )
        db.session.add(
            Organization(slug="test_lab_org", display_name="Test Lab Org", notes=None),
        )
        db.session.commit()
        sid = Source.query.filter_by(url="https://example.org/track").first().id
        oid = Organization.query.filter_by(slug="test_lab_org").first().id

    _login(client)

    rv = client.get(f"/admin/sources/{sid}")
    assert rv.status_code == 200
    assert b"Source owner" in rv.data or b"source-owner-kind" in rv.data

    client.post(
        f"/admin/sources/{sid}",
        data={
            "url": "https://example.org/track",
            "kind": "rss_feed",
            "owner_kind": "organization",
            "owner_organization_id": str(oid),
            "submit": "Save",
        },
        follow_redirects=True,
    )

    with app.app_context():
        src = db.session.get(Source, sid)
        assert src.organization_id == oid
        assert src.person_id is None

    rv2 = client.get(f"/admin/sources/{sid}")
    assert rv2.status_code == 200
    assert str(oid).encode() in rv2.data


def test_organization_new_accepts_slug_from_display_name(app, client):
    _login(client)
    rv = client.post(
        "/admin/organizations/new",
        data={"display_name": "Washington Neuro Lab!", "notes": "", "submit": "Save"},
        follow_redirects=True,
    )
    assert rv.status_code == 200
    with app.app_context():
        row = Organization.query.filter_by(slug="washington_neuro_lab").first()
        assert row is not None
        assert row.display_name == "Washington Neuro Lab!"


def test_organization_new_shows_validation_when_display_yields_empty_slug(app, client):
    _login(client)
    rv = client.post(
        "/admin/organizations/new",
        data={"display_name": "%%%", "notes": "", "submit": "Save"},
        follow_redirects=False,
    )
    assert rv.status_code == 400
    assert b"usable display name" in rv.data.lower() or b"slug" in rv.data.lower()


def test_second_same_display_name_gets_incremented_slug(app, client):
    _login(client)
    for _ in range(2):
        client.post(
            "/admin/organizations/new",
            data={"display_name": "Duplicate Display", "notes": "", "submit": "Save"},
            follow_redirects=True,
        )
    with app.app_context():
        slugs = {o.slug for o in Organization.query.all()}
        assert "duplicate_display" in slugs
        assert "duplicate_display_2" in slugs


def test_people_list_hub_corpus_mark_for_member_person_owned_source(app, client):
    with app.app_context():
        hub = Organization(slug="hub_org", display_name="Hub Org", notes=None)
        db.session.add(hub)
        db.session.commit()
        hid = hub.id
        person = Person(
            slug="member_pi",
            display_name="Member PI",
            notes=None,
        )
        src = Source(
            url="https://hub-member.example.edu/feed",
            kind="rss_feed",
            enabled=True,
            pending=False,
            person_id=None,
            organization_id=None,
        )
        db.session.add_all([person, src])
        db.session.commit()
        pid, sid = person.id, src.id
        sync_person_organizations(person=db.session.get(Person, pid), organization_ids_ordered=[hid])
        src.person_id = pid
        db.session.get(Organization, hid).is_hub = True
        db.session.commit()

    _login(client)
    rv = client.get("/admin/people")
    assert rv.status_code == 200
    assert b"hub-corpus-mark" in rv.data


def test_organizations_list_shows_designated_hub_star(app, client):
    with app.app_context():
        hub = Organization(slug="star_hub", display_name="Star Hub Org", notes=None)
        db.session.add(hub)
        db.session.commit()
        hid = hub.id
        hub.is_hub = True
        db.session.commit()

    _login(client)
    rv = client.get("/admin/organizations")
    assert rv.status_code == 200
    assert b"hub-corpus-mark--designated" in rv.data


def test_person_edit_associates_owned_sources_via_xor(app, client):
    with app.app_context():
        org = Organization(slug="assoc_org", display_name="Assoc Org", notes=None)
        person = Person(slug="assoc_person", display_name="Assoc Person", notes=None)
        src = Source(
            url="https://from-person.example.edu/rss",
            kind="rss_feed",
            enabled=True,
            pending=False,
        )
        db.session.add_all([org, person, src])
        db.session.commit()
        sid, pid, oid = src.id, person.id, org.id
        sync_person_organizations(person=db.session.get(Person, pid), organization_ids_ordered=[oid])
        db.session.commit()

    _login(client)

    rv = client.post(
        f"/admin/people/{pid}/edit",
        data=MultiDict(
            [
                ("display_name", "Assoc Person"),
                ("organization_ids", str(oid)),
                ("notes", ""),
                ("source_ids", str(sid)),
                ("submit", "Save"),
            ]
        ),
        follow_redirects=False,
    )
    assert rv.status_code == 302

    with app.app_context():
        row = db.session.get(Source, sid)
        assert row.person_id == pid
        assert row.organization_id is None

    rv2 = client.get(f"/admin/people/{pid}/edit", follow_redirects=True)
    assert rv2.status_code == 200
    assert b"name=\"source_ids\"" in rv2.data


def test_entities_legacy_admin_path_redirects_to_people(client):
    _login(client)
    rv = client.get("/admin/entities/extra/bits", follow_redirects=False)
    assert rv.status_code == 308
    assert "/admin/people" in (rv.headers.get("Location") or "")


def test_sources_quick_create_prefix_post_links_person_xor(app, client):
    with app.app_context():
        person = Person(slug="qc_person", display_name="QC Person", notes=None)
        db.session.add(person)
        db.session.commit()
        pid = person.id
        next_url = f"/admin/people/{pid}/edit"

    _login(client)
    rv = client.post(
        "/admin/sources/quick-create",
        data={
            "for_person_id": str(pid),
            "for_organization_id": "",
            "quick_src-url": "https://quick-create.example.edu/feed",
            "quick_src-label": "Lab feed",
            "quick_src-kind": "rss_feed",
            "quick_src-hide_from_polling": "",
            "quick_src-submit": "Save",
            "next": next_url,
        },
        follow_redirects=False,
    )
    assert rv.status_code == 302
    assert next_url in (rv.headers.get("Location") or "")

    with app.app_context():
        src = Source.query.filter_by(url="https://quick-create.example.edu/feed").first()
        assert src is not None
        assert src.person_id == pid
        assert src.organization_id is None
        assert src.pending is False


def test_person_edit_xor_change_marks_persona_stale(app, client):
    with app.app_context():
        person = Person(slug="stale_xor", display_name="Stale XOR", notes=None)
        src_a = Source(
            url="https://stale-a.example.edu/rss",
            kind="rss_feed",
            enabled=True,
            pending=False,
        )
        src_b = Source(
            url="https://stale-b.example.edu/rss",
            kind="rss_feed",
            enabled=True,
            pending=False,
        )
        db.session.add_all([person, src_a, src_b])
        db.session.commit()
        pid, sid_a, sid_b = person.id, src_a.id, src_b.id
        src_a.person_id = pid
        src_a.organization_id = None
        db.session.add(PersonaSnapshot(person_id=pid, build_status="ok"))
        db.session.commit()

    _login(client)
    client.post(
        f"/admin/people/{pid}/edit",
        data=MultiDict(
            [
                ("display_name", "Stale XOR"),
                ("notes", ""),
                ("source_ids", str(sid_b)),
                ("submit", "Save"),
            ]
        ),
        follow_redirects=True,
    )

    with app.app_context():
        snap = PersonaSnapshot.query.filter_by(person_id=pid).first()
        assert snap is not None
        assert snap.build_status == "stale"
        moved = db.session.get(Source, sid_b)
        assert moved.person_id == pid


def test_identities_refresh_stale_ready_returns_redirect_when_logged_in(app, client):
    _login(client)
    rv = client.post("/admin/identities/refresh-stale-ready", follow_redirects=False)
    assert rv.status_code == 302
    assert rv.headers.get("Location", "").endswith("/admin/") or "/admin/" in rv.headers.get("Location", "")
