"""Public listability and Latest anti-flood helpers."""

from app import create_app
from app.domain.public_sources import (
    _public_link_dedupe_fingerprint,
    apply_per_source_cap,
    batch_consecutive_by_source,
    dedupe_latest_items_by_source_link,
    organization_is_publicly_listable,
    person_is_publicly_listable,
    publicly_listed_people,
)
from app.extensions import db
from app.models import ContentItem, Organization, Person, Source


def test_public_listability_and_cap(tmp_path):
    db_file = tmp_path / "t.db"
    app = create_app(
        override_config={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
        }
    )
    with app.app_context():
        db.create_all()
        p = Person(slug="pi-one", display_name="PI One")
        db.session.add(p)
        db.session.flush()
        s = Source(
            url="https://example.org/feed",
            kind="rss_feed",
            enabled=True,
            pending=False,
            person_id=p.id,
        )
        db.session.add(s)
        db.session.flush()
        for i in range(6):
            db.session.add(
                ContentItem(
                    source_id=s.id,
                    external_id=f"e{i}",
                    title=f"T{i}",
                    link=f"https://example.org/{i}",
                )
            )
        db.session.commit()

        assert person_is_publicly_listable(p.id)
        assert publicly_listed_people() == [p]

        o = Organization(slug="lab", display_name="Lab")
        db.session.add(o)
        db.session.commit()
        assert not organization_is_publicly_listable(o.id)

        items = (
            ContentItem.query.filter_by(source_id=s.id).order_by(ContentItem.id.desc()).limit(10).all()
        )
        capped = apply_per_source_cap(items, max_per_source=2, take_total=10)
        assert len(capped) == 2

        grouped = batch_consecutive_by_source(capped, min_batch=2)
        assert grouped and grouped[0]["kind"] == "batch"


def test_pubmed_same_pmid_different_tracking_collapses():
    a = "https://pubmed.ncbi.nlm.nih.gov/38293211/?utm_source=Other&utm_medium=rss&utm_campaign=pubmed-2"
    b = "https://pubmed.ncbi.nlm.nih.gov/38293211/?fc=20260502170815&ff=20260502172056&v=2.19.0"
    assert _public_link_dedupe_fingerprint(a) == _public_link_dedupe_fingerprint(b) == "https://pubmed.ncbi.nlm.nih.gov/38293211"


def test_dedupe_latest_items_same_source_same_link(tmp_path):
    db_file = tmp_path / "d.db"
    app = create_app(
        override_config={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
        }
    )
    with app.app_context():
        db.create_all()
        p = Person(slug="p-dedupe", display_name="P Dedupe")
        db.session.add(p)
        db.session.flush()
        s = Source(
            url="https://example.org/page",
            kind="html_page",
            enabled=True,
            pending=False,
            person_id=p.id,
        )
        db.session.add(s)
        db.session.flush()
        for i in range(4):
            db.session.add(
                ContentItem(
                    source_id=s.id,
                    external_id=f"sha256:{'a' * (i + 1)}",
                    title=f"Title pass {i}",
                    link="https://example.org/page",
                )
            )
        db.session.commit()
        items = ContentItem.query.filter_by(source_id=s.id).order_by(ContentItem.id.desc()).all()
        deduped = dedupe_latest_items_by_source_link(items)
        assert len(deduped) == 1
        assert deduped[0].title == "Title pass 3"
