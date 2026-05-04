"""Organization rollup excerpt assembly prioritizes org-attached sources."""

from datetime import datetime, timedelta, timezone

from app import create_app
from app.extensions import db
from app.identity.rollup import _thin_excerpts_for_org
from app.models import ContentItem, Organization, Person, Source


def test_org_attached_sources_listed_before_member_and_cap_member(tmp_path):
    db_file = tmp_path / "r.db"
    app = create_app(
        override_config={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
        }
    )
    with app.app_context():
        db.create_all()
        o = Organization(slug="psych", display_name="Department of Psychiatry")
        p = Person(slug="pi", display_name="Kravitz")
        db.session.add_all([o, p])
        db.session.flush()
        p.organizations.append(o)

        s_org = Source(
            url="https://psychiatry.wustl.edu/about/",
            kind="html_page",
            organization_id=o.id,
            pending=False,
            enabled=True,
        )
        s_mem = Source(
            url="https://pi.example/feed.xml",
            kind="rss_feed",
            person_id=p.id,
            pending=False,
            enabled=True,
        )
        db.session.add_all([s_org, s_mem])
        db.session.flush()

        base = datetime.now(timezone.utc)
        db.session.add(
            ContentItem(
                source_id=s_org.id,
                external_id="mainsha:orgpage",
                title="About — Psychiatry",
                snippet="Department mission and training programs.",
                first_seen_at=base - timedelta(days=30),
            )
        )
        for i in range(15):
            db.session.add(
                ContentItem(
                    source_id=s_mem.id,
                    external_id=f"e{i}",
                    title=f"Paper {i}",
                    snippet="Neural circuits and behavior.",
                    first_seen_at=base - timedelta(hours=i),
                )
            )
        db.session.commit()

        text = _thin_excerpts_for_org(o.id, cap_items=24)
        assert text.startswith("OFFICIAL_ORG_SOURCES\n")
        assert "About — Psychiatry" in text
        assert "MEMBER_AFFILIATED_SOURCES\n" in text
        # Member slice capped: at most 10 "Paper" lines when org-owned sources exist
        assert text.count("title=Paper") <= 10
