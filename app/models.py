"""SQLAlchemy models for Synapse MVP."""

from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db


class Source(db.Model):
    __tablename__ = "source"

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(2048), nullable=False, unique=True)
    kind = db.Column(db.String(32), nullable=False)  # rss_feed | html_page
    label = db.Column(db.String(512))
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    pending = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    content_items = db.relationship("ContentItem", back_populates="source", cascade="all,delete-orphan")
    snapshots = db.relationship("SourceSnapshot", back_populates="source", cascade="all,delete-orphan")


class ContentItem(db.Model):
    __tablename__ = "content_item"

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("source.id", ondelete="CASCADE"), nullable=False)
    external_id = db.Column(db.String(512), nullable=False)
    title = db.Column(db.Text)
    link = db.Column(db.String(4096))
    published_at = db.Column(db.DateTime(timezone=True))
    snippet = db.Column(db.Text)
    first_seen_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    source = db.relationship("Source", back_populates="content_items")
    lead_candidates = db.relationship("LeadCandidate", back_populates="content_item", cascade="all,delete-orphan")

    __table_args__ = (db.UniqueConstraint("source_id", "external_id", name="uq_content_item_source_external"),)


class SourceSnapshot(db.Model):
    __tablename__ = "source_snapshot"

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("source.id", ondelete="CASCADE"), nullable=False)
    fetched_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    body_sha256 = db.Column(db.String(64), nullable=False)

    source = db.relationship("Source", back_populates="snapshots")


class LeadCandidate(db.Model):
    __tablename__ = "lead_candidate"

    id = db.Column(db.Integer, primary_key=True)
    content_item_id = db.Column(db.Integer, db.ForeignKey("content_item.id", ondelete="CASCADE"), nullable=False)
    headline = db.Column(db.Text, nullable=False)
    angle = db.Column(db.Text)
    outreach_snippet = db.Column(db.Text)
    hub_tags = db.Column(db.Text)
    status = db.Column(db.String(32), nullable=False, default="new")
    model_used = db.Column(db.String(128))
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    content_item = db.relationship("ContentItem", back_populates="lead_candidates")


class PollLog(db.Model):
    """Last-run trail for Poll now (admin dashboard)."""

    __tablename__ = "poll_log"

    id = db.Column(db.Integer, primary_key=True)
    ran_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    ok = db.Column(db.Boolean, nullable=False, default=False)
    detail = db.Column(db.Text)  # human-readable summary or traceback tail
