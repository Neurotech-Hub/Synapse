"""SQLAlchemy models for Synapse MVP."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db

person_organization = db.Table(
    "person_organization",
    db.Column("person_id", db.Integer, db.ForeignKey("person.id", ondelete="CASCADE"), primary_key=True),
    db.Column("organization_id", db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), primary_key=True),
)

region_building = db.Table(
    "region_building",
    db.Column("region_id", db.Integer, db.ForeignKey("region.id", ondelete="CASCADE"), primary_key=True),
    db.Column("building_id", db.Integer, db.ForeignKey("building.id", ondelete="CASCADE"), primary_key=True),
)


class Organization(db.Model):
    __tablename__ = "organization"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), nullable=False, unique=True)
    display_name = db.Column(db.String(512), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    #: Set by ingest when new public content may warrant a new public digest (cleared when digest build succeeds).
    public_digest_stale = db.Column(db.Boolean, nullable=False, default=False)
    #: True for the Neurotech Hub org — persona synced from hub_persona.json, not rebuilt by LLM.
    is_hub = db.Column(db.Boolean, nullable=False, default=False)

    building_id = db.Column(db.Integer, db.ForeignKey("building.id", ondelete="SET NULL"), nullable=True)

    people = db.relationship("Person", secondary=person_organization, back_populates="organizations")
    building = db.relationship("Building", foreign_keys=[building_id], back_populates="organizations")


class Person(db.Model):
    __tablename__ = "person"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), nullable=False, unique=True)
    display_name = db.Column(db.String(512), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    public_digest_stale = db.Column(db.Boolean, nullable=False, default=False)

    organizations = db.relationship("Organization", secondary=person_organization, back_populates="people")


class Region(db.Model):
    """Map-drawn area (GeoJSON polygon stored as text)."""

    __tablename__ = "region"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), nullable=False, unique=True)
    region_name = db.Column(db.String(512), nullable=False)
    geojson = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    buildings_explicit = db.relationship(
        "Building",
        foreign_keys="Building.region_id",
        back_populates="region",
        passive_deletes=True,
    )


class Building(db.Model):
    __tablename__ = "building"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), nullable=False, unique=True)
    display_name = db.Column(db.String(512), nullable=False)
    #: Short label (may match display_name for migrated rows).
    place_name = db.Column(db.String(512), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    region_id = db.Column(db.Integer, db.ForeignKey("region.id", ondelete="SET NULL"), nullable=True)
    region = db.relationship("Region", foreign_keys=[region_id], back_populates="buildings_explicit")

    organizations = db.relationship("Organization", back_populates="building", foreign_keys="Organization.building_id")


class PersonaSnapshot(db.Model):
    """CM ``PIPersona``-aligned snapshot for a person, organization, or building (built via Ollama)."""

    __tablename__ = "persona_snapshot"
    __table_args__ = (
        CheckConstraint(
            "(person_id IS NOT NULL AND organization_id IS NULL AND building_id IS NULL) OR "
            "(person_id IS NULL AND organization_id IS NOT NULL AND building_id IS NULL) OR "
            "(person_id IS NULL AND organization_id IS NULL AND building_id IS NOT NULL)",
            name="ck_persona_snapshot_subject_xor",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id", ondelete="CASCADE"), unique=True, nullable=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), unique=True, nullable=True
    )
    building_id = db.Column(db.Integer, db.ForeignKey("building.id", ondelete="CASCADE"), unique=True, nullable=True)

    research_focus = db.Column(db.JSON, nullable=False, default=list)
    methods = db.Column(db.JSON, nullable=False, default=list)
    keywords = db.Column(db.JSON, nullable=False, default=list)
    current_projects = db.Column(db.JSON, nullable=False, default=list)
    funding_signals = db.Column(db.JSON, nullable=False, default=list)
    collab_openness_score = db.Column(db.Float, nullable=True)
    hardware_interests = db.Column(db.JSON, nullable=True, default=list)
    infrastructure_needs = db.Column(db.JSON, nullable=True, default=list)
    paper_count_last_90d = db.Column(db.Integer, nullable=False, default=0)
    raw_papers_snapshot = db.Column(db.JSON, nullable=False, default=list)
    notes = db.Column(db.Text, nullable=True)
    sources_last_scanned = db.Column(db.JSON, nullable=False, default=dict)
    prompt_version = db.Column(db.String(64), nullable=False, default="1")
    model_used = db.Column(db.String(128), nullable=True)
    input_fingerprint = db.Column(db.String(128), nullable=True)
    build_status = db.Column(db.String(32), nullable=False, default="ok")  # ok | failed | stale
    build_error = db.Column(db.Text, nullable=True)
    generated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    person = db.relationship(
        "Person",
        foreign_keys=[person_id],
        backref=db.backref("persona", uselist=False, cascade="all, delete-orphan"),
    )
    organization = db.relationship(
        "Organization",
        foreign_keys=[organization_id],
        backref=db.backref("persona", uselist=False, cascade="all, delete-orphan"),
    )
    building = db.relationship(
        "Building",
        foreign_keys=[building_id],
        backref=db.backref("persona", uselist=False, cascade="all, delete-orphan"),
    )


class Source(db.Model):
    __tablename__ = "source"
    __table_args__ = (
        CheckConstraint(
            "(person_id IS NULL OR organization_id IS NULL)",
            name="ck_source_person_org_xor_null",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(2048), nullable=False, unique=True)
    label = db.Column(db.String(512), nullable=True)
    kind = db.Column(db.String(32), nullable=False)  # rss_feed | html_page
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    pending = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    #: Public submit hints intended owner classification (approved in admin sets XOR FK).
    ownership_hint = db.Column(db.String(32), nullable=True)  # person | organization

    person_id = db.Column(db.Integer, db.ForeignKey("person.id", ondelete="SET NULL"), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id", ondelete="SET NULL"), nullable=True)

    person = db.relationship("Person", backref="owned_sources")
    organization = db.relationship("Organization", backref="owned_sources")

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

    public_feed_verdict = db.Column(db.String(8), nullable=True)  # NULL | show | hide
    public_feed_display_title = db.Column(db.Text, nullable=True)
    public_feed_display_blurb = db.Column(db.Text, nullable=True)
    public_feed_input_fingerprint = db.Column(db.String(128), nullable=True)
    public_feed_curated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    public_feed_model_used = db.Column(db.String(128), nullable=True)

    source = db.relationship("Source", back_populates="content_items")

    __table_args__ = (db.UniqueConstraint("source_id", "external_id", name="uq_content_item_source_external"),)

    @property
    def public_latest_card_title(self) -> str:
        from app.domain.public_feed_display import effective_public_latest_title

        return effective_public_latest_title(self)

    @property
    def public_latest_card_snippet(self) -> str | None:
        from app.domain.public_feed_display import effective_public_latest_snippet

        return effective_public_latest_snippet(self)


class SourceSnapshot(db.Model):
    __tablename__ = "source_snapshot"

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("source.id", ondelete="CASCADE"), nullable=False)
    fetched_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    body_sha256 = db.Column(db.String(64), nullable=False)

    source = db.relationship("Source", back_populates="snapshots")


class PublicActivityDigest(db.Model):
    """Audience-facing digest of recent ingest for one person or organization (separate from admin LeadReport)."""

    __tablename__ = "public_activity_digest"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN person_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN organization_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_public_activity_digest_target_one",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id", ondelete="CASCADE"), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), nullable=True)

    summary_text = db.Column(db.Text, nullable=True)
    cited_content_item_ids_json = db.Column(db.Text, nullable=True)
    input_fingerprint = db.Column(db.String(128), nullable=True)
    prompt_version = db.Column(db.String(64), nullable=False, default="1")
    model_used = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="ok")  # ok | failed
    error_detail = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    person = db.relationship("Person", foreign_keys=[person_id], backref="public_activity_digests")
    organization = db.relationship("Organization", foreign_keys=[organization_id], backref="public_activity_digests")


class LeadReport(db.Model):
    """Hub-centric synthesis run against one person, organization, building, or region (multi-step LLM)."""

    __tablename__ = "lead_report"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN target_person_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN target_organization_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN target_building_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN target_region_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_lead_report_target_one",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    hub_organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id", ondelete="SET NULL"), nullable=True
    )

    target_person_id = db.Column(db.Integer, db.ForeignKey("person.id", ondelete="CASCADE"), nullable=True)
    target_organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), nullable=True
    )
    target_building_id = db.Column(db.Integer, db.ForeignKey("building.id", ondelete="CASCADE"), nullable=True)
    target_region_id = db.Column(db.Integer, db.ForeignKey("region.id", ondelete="CASCADE"), nullable=True)

    status = db.Column(db.String(24), nullable=False, default="queued")  # queued|running|ok|failed
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    executive_summary = db.Column(db.Text, nullable=True)
    collaboration_routes_json = db.Column(db.Text, nullable=True)
    ranked_contacts_json = db.Column(db.Text, nullable=True)

    fit_score = db.Column(db.Float, nullable=True)
    email_draft = db.Column(db.Text, nullable=True)
    positive_signals = db.Column(db.JSON, nullable=False, default=list)
    uncertainties = db.Column(db.JSON, nullable=False, default=list)
    likely_technical_pain = db.Column(db.Text, nullable=True)

    input_fingerprint = db.Column(db.String(128), nullable=True)
    model_used = db.Column(db.String(128), nullable=True)
    error_detail = db.Column(db.Text, nullable=True)

    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    review_notes = db.Column(db.Text, nullable=True)

    hub_organization = db.relationship("Organization", foreign_keys=[hub_organization_id])
    target_person = db.relationship("Person", foreign_keys=[target_person_id])
    target_organization = db.relationship("Organization", foreign_keys=[target_organization_id])
    target_building = db.relationship("Building", foreign_keys=[target_building_id])
    target_region = db.relationship("Region", foreign_keys=[target_region_id])


class PollLog(db.Model):
    __tablename__ = "poll_log"

    id = db.Column(db.Integer, primary_key=True)
    ran_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    ok = db.Column(db.Boolean, nullable=False, default=False)
    detail = db.Column(db.Text)


