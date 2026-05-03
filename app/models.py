"""SQLAlchemy models for Synapse MVP."""

from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db

source_entity_tbl = db.Table(
    "source_entity",
    db.Column("source_id", db.Integer, db.ForeignKey("source.id", ondelete="CASCADE"), primary_key=True),
    db.Column("entity_id", db.Integer, db.ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True),
)


class Source(db.Model):
    __tablename__ = "source"

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(2048), nullable=False, unique=True)
    kind = db.Column(db.String(32), nullable=False)  # rss_feed | html_page
    label = db.Column(db.String(512))
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    pending = db.Column(db.Boolean, nullable=False, default=False)
    #: Hub “ours” vs external trackers — used for lead qualification corpus split.
    lead_source = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    content_items = db.relationship("ContentItem", back_populates="source", cascade="all,delete-orphan")
    snapshots = db.relationship("SourceSnapshot", back_populates="source", cascade="all,delete-orphan")
    entities = db.relationship("Entity", secondary=source_entity_tbl, back_populates="sources")


class Entity(db.Model):
    __tablename__ = "entity"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), nullable=False, unique=True)
    #: lab | person | place | org (enforced in forms / admin)
    kind = db.Column(db.String(32), nullable=False)
    display_name = db.Column(db.String(512), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    sources = db.relationship("Source", secondary=source_entity_tbl, back_populates="entities")


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
    lead_candidates = db.relationship(
        "LeadCandidate",
        back_populates="candidate_content_item",
        foreign_keys="LeadCandidate.candidate_content_item_id",
        cascade="all,delete-orphan",
    )
    hub_anchor_for_leads = db.relationship(
        "LeadCandidate",
        back_populates="anchor_hub_content_item",
        foreign_keys="LeadCandidate.anchor_hub_content_item_id",
    )

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
    #: World / external content item this lead is grounded in (DB column: content_item_id).
    candidate_content_item_id = db.Column(
        "content_item_id",
        db.Integer,
        db.ForeignKey("content_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    anchor_hub_content_item_id = db.Column(
        db.Integer, db.ForeignKey("content_item.id", ondelete="SET NULL"), nullable=True
    )
    #: JSON array of hub ContentItem ids (audit trail for prompt context).
    hub_cited_content_item_ids = db.Column(db.Text)
    hub_context_hash = db.Column(db.String(128), nullable=False)
    prompt_version = db.Column(db.String(64), nullable=False)
    entity_id = db.Column(db.Integer, db.ForeignKey("entity.id", ondelete="SET NULL"), nullable=True)
    subject_fingerprint = db.Column(db.String(512), nullable=True)

    headline = db.Column(db.Text, nullable=False)
    angle = db.Column(db.Text)
    outreach_snippet = db.Column(db.Text)
    hub_tags = db.Column(db.Text)
    status = db.Column(db.String(32), nullable=False, default="new")
    model_used = db.Column(db.String(128))
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    candidate_content_item = db.relationship(
        "ContentItem",
        foreign_keys=[candidate_content_item_id],
        back_populates="lead_candidates",
    )
    anchor_hub_content_item = db.relationship(
        "ContentItem",
        foreign_keys=[anchor_hub_content_item_id],
        back_populates="hub_anchor_for_leads",
    )
    entity = db.relationship("Entity", backref="lead_candidates")

    __table_args__ = (
        db.UniqueConstraint(
            "content_item_id",
            "prompt_version",
            "hub_context_hash",
            name="uq_lead_qual_candidate_prompt_hash",
        ),
    )


class LeadGenWatermark(db.Model):
    """Monotonic cursor for lead qualification over world ContentItem ids."""

    __tablename__ = "lead_gen_watermark"

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(64), nullable=False, unique=True)
    last_candidate_content_item_id = db.Column(db.Integer, nullable=True)


class PollLog(db.Model):
    """Last-run trail for Poll now (admin dashboard)."""

    __tablename__ = "poll_log"

    id = db.Column(db.Integer, primary_key=True)
    ran_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    ok = db.Column(db.Boolean, nullable=False, default=False)
    detail = db.Column(db.Text)  # human-readable summary or traceback tail


class LeadPipelineSettings(db.Model):
    """Singleton row (``id`` = 1): admin-editable lead qualification toggles and caps."""

    __tablename__ = "lead_pipeline_settings"

    id = db.Column(db.Integer, primary_key=True)
    qualify_enabled = db.Column(db.Boolean, nullable=False, default=False)
    prompt_version = db.Column(db.String(64), nullable=False, default="1")
    #: When set, used instead of ``prompts/qualified_lead.txt`` (admin-editable).
    qualified_lead_prompt_body = db.Column(db.Text, nullable=True)
    max_hub_items = db.Column(db.Integer, nullable=False, default=25)
    max_candidates_per_run = db.Column(db.Integer, nullable=False, default=30)
    entity_catalog_max = db.Column(db.Integer, nullable=False, default=40)
