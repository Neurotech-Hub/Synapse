"""Organization effective source sets for identity rollup."""

from app import create_app
from app.domain.effective_sources import (
    identity_eligible_source_ids_for_organization,
    source_ids_for_organization,
)
from app.extensions import db
from app.models import Organization, Person, Source


def test_source_ids_for_organization_union(tmp_path):
    db_file = tmp_path / "t.db"
    app = create_app(
        override_config={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
        }
    )
    with app.app_context():
        db.create_all()
        o = Organization(slug="org", display_name="Org")
        p = Person(slug="p", display_name="P")
        db.session.add_all([o, p])
        db.session.flush()
        p.organizations.append(o)
        s_org = Source(url="https://a.example/feed", kind="rss_feed", organization_id=o.id)
        s_p = Source(url="https://b.example/feed", kind="rss_feed", person_id=p.id, pending=False, enabled=True)
        db.session.add_all([s_org, s_p])
        db.session.commit()
        assert source_ids_for_organization(o.id) == {s_org.id, s_p.id}


def test_identity_eligible_excludes_pending_disabled(tmp_path):
    db_file = tmp_path / "t2.db"
    app = create_app(
        override_config={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
        }
    )
    with app.app_context():
        db.create_all()
        o = Organization(slug="lab", display_name="Lab")
        db.session.add(o)
        db.session.flush()
        s_ok = Source(url="https://ok.example/feed", kind="rss_feed", organization_id=o.id, pending=False, enabled=True)
        s_pending = Source(
            url="https://pend.example/feed", kind="rss_feed", organization_id=o.id, pending=True, enabled=True
        )
        s_off = Source(
            url="https://off.example/feed", kind="rss_feed", organization_id=o.id, pending=False, enabled=False
        )
        db.session.add_all([s_ok, s_pending, s_off])
        db.session.commit()
        assert identity_eligible_source_ids_for_organization(o.id) == [s_ok.id]
