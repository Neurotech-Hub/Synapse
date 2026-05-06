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
    last_poll_at = db.Column(db.DateTime(timezone=True), nullable=True)

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


class FundingOpportunity(db.Model):
    """Lightweight funding opportunity record imported or curated by an operator."""

    __tablename__ = "funding_opportunity"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'expired', 'archived')",
            name="ck_funding_opportunity_status",
        ),
        CheckConstraint(
            "source_type IN ('manual', 'csv', 'imported', 'url_fetch', 'fetched_url', 'rss', 'public_search')",
            name="ck_funding_opportunity_source_type",
        ),
        CheckConstraint(
            "effort_index IN ('mild', 'moderate', 'heavy', 'unknown')",
            name="ck_funding_opportunity_effort_index",
        ),
        CheckConstraint(
            "synthesis_status IN ('not_started', 'fetched', 'synthesized', 'failed', 'needs_review')",
            name="ck_funding_opportunity_synthesis_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(180), nullable=False, unique=True)
    external_id = db.Column(db.String(256), nullable=True, unique=True)
    title = db.Column(db.String(300), nullable=False)
    sponsor_name = db.Column(db.String(200), nullable=True)
    source_url = db.Column(db.Text, nullable=True)
    normalized_source_url = db.Column(db.String(2048), nullable=True, unique=True)
    source_type = db.Column(db.String(40), nullable=False, default="manual")

    status = db.Column(db.String(40), nullable=False, default="draft")  # draft | active | expired | archived
    is_public = db.Column(db.Boolean, nullable=False, default=False)
    is_reviewed = db.Column(db.Boolean, nullable=False, default=False)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    deadline_date = db.Column(db.Date, nullable=True)
    deadline_text = db.Column(db.String(300), nullable=True)
    amount_min = db.Column(db.Integer, nullable=True)
    amount_max = db.Column(db.Integer, nullable=True)
    amount_text = db.Column(db.String(300), nullable=True)
    mechanism = db.Column(db.String(160), nullable=True)

    effort_index = db.Column(db.String(40), nullable=False, default="unknown")
    effort_score = db.Column(db.Float, nullable=True)
    effort_confidence = db.Column(db.Float, nullable=True)
    effort_rationale = db.Column(db.Text, nullable=True)
    effort_signals_json = db.Column(db.JSON, nullable=False, default=list)
    effort_reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    summary_public = db.Column(db.Text, nullable=True)
    summary_private = db.Column(db.Text, nullable=True)
    eligibility_summary = db.Column(db.Text, nullable=True)
    notes_private = db.Column(db.Text, nullable=True)

    topic_tags_json = db.Column(db.JSON, nullable=False, default=list)
    method_tags_json = db.Column(db.JSON, nullable=False, default=list)
    hub_relevance_json = db.Column(db.JSON, nullable=False, default=list)

    raw_text = db.Column(db.Text, nullable=True)
    raw_text_hash = db.Column(db.String(64), nullable=True, index=True)
    source_url_final = db.Column(db.String(2048), nullable=True)
    fetch_status_code = db.Column(db.Integer, nullable=True)
    fetch_content_type = db.Column(db.String(160), nullable=True)
    fetch_error = db.Column(db.Text, nullable=True)
    fetched_at = db.Column(db.DateTime(timezone=True), nullable=True)
    source_text_chars = db.Column(db.Integer, nullable=True)
    synthesized_json = db.Column(db.JSON, nullable=True)
    synthesis_status = db.Column(db.String(40), nullable=False, default="not_started")
    synthesis_provider = db.Column(db.String(40), nullable=True)
    synthesis_model = db.Column(db.String(120), nullable=True)
    synthesis_fingerprint = db.Column(db.String(128), nullable=True)
    synthesis_generated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    synthesis_confidence = db.Column(db.Float, nullable=True)
    synthesis_error = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)


class Idea(db.Model):
    """Curated research or technical concept used for public discovery and future matching."""

    __tablename__ = "idea"
    __table_args__ = (
        CheckConstraint(
            "idea_type IN ("
            "'research_theme', 'technical_capability', 'buildable_concept', 'method_cluster', "
            "'funding_theme', 'strategic_area', 'public_resource_topic', 'unknown'"
            ")",
            name="ck_idea_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'review', 'public', 'private', 'archived', 'hidden', 'merged')",
            name="ck_idea_status",
        ),
        CheckConstraint(
            "created_via IN ('manual', 'persona_extract', 'content_extract', 'funding_extract', 'admin_seed', 'imported')",
            name="ck_idea_created_via",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(240), nullable=False)
    slug = db.Column(db.String(260), nullable=False, unique=True)

    idea_type = db.Column(db.String(50), nullable=False, default="unknown")
    status = db.Column(db.String(40), nullable=False, default="draft")
    is_public = db.Column(db.Boolean, nullable=False, default=False)
    is_reviewed = db.Column(db.Boolean, nullable=False, default=False)

    short_description = db.Column(db.String(500), nullable=True)
    public_summary = db.Column(db.Text, nullable=True)
    private_summary = db.Column(db.Text, nullable=True)

    hub_relevance = db.Column(db.Text, nullable=True)
    buildable_angle = db.Column(db.Text, nullable=True)
    funding_angle = db.Column(db.Text, nullable=True)

    tags_json = db.Column(db.JSON, nullable=False, default=list)
    aliases_json = db.Column(db.JSON, nullable=False, default=list)
    hub_capabilities_json = db.Column(db.JSON, nullable=False, default=list)
    evidence_refs_json = db.Column(db.JSON, nullable=False, default=list)
    synthesized_json = db.Column(db.JSON, nullable=True)

    confidence_score = db.Column(db.Float, nullable=True)
    quality_flags_json = db.Column(db.JSON, nullable=False, default=list)

    created_by = db.Column(db.String(80), nullable=True)
    created_via = db.Column(db.String(40), nullable=False, default="manual")

    generated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)


class IdeaSuggestion(db.Model):
    """Reviewable candidate Idea generated from existing evidence."""

    __tablename__ = "idea_suggestion"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('persona_snapshot', 'content_item', 'person', 'organization', 'building', 'region')",
            name="ck_idea_suggestion_source_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'merged')",
            name="ck_idea_suggestion_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    source_type = db.Column(db.String(64), nullable=False)
    source_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(240), nullable=False)
    idea_type = db.Column(db.String(50), nullable=False, default="unknown")
    short_description = db.Column(db.String(500), nullable=True)
    public_summary = db.Column(db.Text, nullable=True)
    tags_json = db.Column(db.JSON, nullable=False, default=list)
    aliases_json = db.Column(db.JSON, nullable=False, default=list)
    hub_capabilities_json = db.Column(db.JSON, nullable=False, default=list)
    evidence_json = db.Column(db.JSON, nullable=False, default=list)
    duplicate_candidate_id = db.Column(db.Integer, db.ForeignKey("idea.id", ondelete="SET NULL"), nullable=True)
    duplicate_reason = db.Column(db.Text, nullable=True)
    duplicate_confidence = db.Column(db.Float, nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="pending")
    llm_run_id = db.Column(db.Integer, db.ForeignKey("llm_run.id", ondelete="SET NULL"), nullable=True)
    accepted_idea_id = db.Column(db.Integer, db.ForeignKey("idea.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    duplicate_candidate = db.relationship("Idea", foreign_keys=[duplicate_candidate_id])
    accepted_idea = db.relationship("Idea", foreign_keys=[accepted_idea_id])
    llm_run = db.relationship("LLMRun", foreign_keys=[llm_run_id])


class MatchRun(db.Model):
    """Auditable record for one bounded matching pass."""

    __tablename__ = "match_run"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'ok', 'failed')",
            name="ck_match_run_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_type = db.Column(db.String(80), nullable=False)
    source_type = db.Column(db.String(64), nullable=True)
    source_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="queued")

    provider = db.Column(db.String(32), nullable=True)
    model_name = db.Column(db.String(120), nullable=True)
    prompt_version = db.Column(db.String(80), nullable=True)
    pipeline_version = db.Column(db.String(80), nullable=False, default="deterministic_v1")

    candidates_count = db.Column(db.Integer, nullable=False, default=0)
    scored_count = db.Column(db.Integer, nullable=False, default=0)
    accepted_count = db.Column(db.Integer, nullable=False, default=0)
    error_count = db.Column(db.Integer, nullable=False, default=0)

    input_fingerprint = db.Column(db.String(128), nullable=True)
    params_json = db.Column(db.JSON, nullable=False, default=dict)
    result_summary_json = db.Column(db.JSON, nullable=False, default=dict)
    error_text = db.Column(db.Text, nullable=True)

    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MatchEdge(db.Model):
    """Scored private relationship between two supported entity records."""

    __tablename__ = "match_edge"
    __table_args__ = (
        CheckConstraint(
            "status IN ('candidate', 'scored', 'needs_review', 'reviewed', 'accepted', 'rejected', 'hidden', 'archived', 'stale')",
            name="ck_match_edge_status",
        ),
        CheckConstraint(
            "visibility IN ('private', 'public_safe', 'public', 'hidden')",
            name="ck_match_edge_visibility",
        ),
        db.UniqueConstraint(
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            "match_type",
            name="uq_match_edge_pair_type",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    match_run_id = db.Column(db.Integer, db.ForeignKey("match_run.id", ondelete="SET NULL"), nullable=True)
    source_type = db.Column(db.String(64), nullable=False)
    source_id = db.Column(db.Integer, nullable=False)
    target_type = db.Column(db.String(64), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    match_type = db.Column(db.String(80), nullable=False)

    score_total = db.Column(db.Float, nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    score_topic_fit = db.Column(db.Float, nullable=True)
    score_method_fit = db.Column(db.Float, nullable=True)
    score_hub_fit = db.Column(db.Float, nullable=True)
    score_funding_fit = db.Column(db.Float, nullable=True)
    score_evidence_strength = db.Column(db.Float, nullable=True)
    score_recency = db.Column(db.Float, nullable=True)
    score_strategic_value = db.Column(db.Float, nullable=True)
    score_effort_reasonableness = db.Column(db.Float, nullable=True)

    rationale = db.Column(db.Text, nullable=True)
    public_rationale = db.Column(db.Text, nullable=True)
    private_rationale = db.Column(db.Text, nullable=True)
    evidence_json = db.Column(db.JSON, nullable=False, default=list)
    features_json = db.Column(db.JSON, nullable=False, default=dict)
    synthesized_json = db.Column(db.JSON, nullable=True)

    provider = db.Column(db.String(32), nullable=True)
    model_name = db.Column(db.String(120), nullable=True)
    prompt_version = db.Column(db.String(80), nullable=True)
    pipeline_version = db.Column(db.String(80), nullable=False, default="deterministic_v1")
    input_fingerprint = db.Column(db.String(128), nullable=True)

    status = db.Column(db.String(32), nullable=False, default="needs_review")
    visibility = db.Column(db.String(32), nullable=False, default="private")

    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

    run = db.relationship("MatchRun", backref=db.backref("edges", passive_deletes=True))


class CollaborationHypothesis(db.Model):
    """Private evidence-backed lead hypothesis built from accepted matches."""

    __tablename__ = "collaboration_hypothesis"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'needs_review', 'reviewed', 'active', 'contacted', 'dismissed', 'archived', 'stale')",
            name="ck_collaboration_hypothesis_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'normal', 'high', 'strategic')",
            name="ck_collaboration_hypothesis_priority",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(240), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="draft")
    priority = db.Column(db.String(32), nullable=False, default="normal")

    target_type = db.Column(db.String(64), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    idea_id = db.Column(db.Integer, db.ForeignKey("idea.id", ondelete="SET NULL"), nullable=True)
    funding_opportunity_id = db.Column(
        db.Integer,
        db.ForeignKey("funding_opportunity.id", ondelete="SET NULL"),
        nullable=True,
    )
    primary_match_edge_id = db.Column(db.Integer, db.ForeignKey("match_edge.id", ondelete="SET NULL"), nullable=True)
    related_match_edge_ids_json = db.Column(db.JSON, nullable=False, default=list)

    hypothesis_summary = db.Column(db.Text, nullable=True)
    evidence_summary = db.Column(db.Text, nullable=True)
    hub_fit_summary = db.Column(db.Text, nullable=True)
    funding_fit_summary = db.Column(db.Text, nullable=True)
    effort_summary = db.Column(db.Text, nullable=True)
    recommended_action = db.Column(db.Text, nullable=True)
    outreach_angle = db.Column(db.Text, nullable=True)
    public_safe_summary = db.Column(db.Text, nullable=True)
    private_notes = db.Column(db.Text, nullable=True)

    score_fit = db.Column(db.Float, nullable=True)
    score_timing = db.Column(db.Float, nullable=True)
    score_funding = db.Column(db.Float, nullable=True)
    score_effort = db.Column(db.Float, nullable=True)
    score_relationship = db.Column(db.Float, nullable=True)
    score_strategic = db.Column(db.Float, nullable=True)
    score_total = db.Column(db.Float, nullable=True)
    score_breakdown_json = db.Column(db.JSON, nullable=False, default=dict)
    evidence_json = db.Column(db.JSON, nullable=False, default=list)
    synthesized_json = db.Column(db.JSON, nullable=True)

    provider = db.Column(db.String(32), nullable=True)
    model_name = db.Column(db.String(120), nullable=True)
    prompt_version = db.Column(db.String(80), nullable=True)
    pipeline_version = db.Column(db.String(80), nullable=False, default="deterministic_v1")
    input_fingerprint = db.Column(db.String(128), nullable=True)

    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    contacted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    idea = db.relationship("Idea", foreign_keys=[idea_id])
    funding_opportunity = db.relationship("FundingOpportunity", foreign_keys=[funding_opportunity_id])
    primary_match_edge = db.relationship("MatchEdge", foreign_keys=[primary_match_edge_id])


class LLMRun(db.Model):
    """Durable audit row for a prompt execution attempt."""

    __tablename__ = "llm_run"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'ok', 'failed', 'validation_failed', 'skipped')",
            name="ck_llm_run_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    prompt_name = db.Column(db.String(120), nullable=False)
    prompt_version = db.Column(db.String(80), nullable=False)
    provider = db.Column(db.String(32), nullable=False)
    model_name = db.Column(db.String(120), nullable=True)
    input_fingerprint = db.Column(db.String(128), nullable=False, index=True)
    rendered_prompt_hash = db.Column(db.String(64), nullable=False)
    output_hash = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="queued")
    error_message = db.Column(db.Text, nullable=True)
    validation_errors_json = db.Column(db.JSON, nullable=False, default=list)
    latency_ms = db.Column(db.Integer, nullable=True)
    estimated_input_tokens = db.Column(db.Integer, nullable=True)
    estimated_output_tokens = db.Column(db.Integer, nullable=True)
    estimated_cost_usd = db.Column(db.Float, nullable=True)
    source_type = db.Column(db.String(64), nullable=True)
    source_id = db.Column(db.Integer, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)


class PollLog(db.Model):
    __tablename__ = "poll_log"

    id = db.Column(db.Integer, primary_key=True)
    ran_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    ok = db.Column(db.Boolean, nullable=False, default=False)
    detail = db.Column(db.Text)


