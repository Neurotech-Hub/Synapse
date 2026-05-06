"""add funding opportunity table

Revision ID: h1c2d3e4f5a6
Revises: g2b3c4d5e6f7
Create Date: 2026-05-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "h1c2d3e4f5a6"
down_revision = "g2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "funding_opportunity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("sponsor_name", sa.String(length=200), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("normalized_source_url", sa.String(length=2048), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_reviewed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_date", sa.Date(), nullable=True),
        sa.Column("deadline_text", sa.String(length=300), nullable=True),
        sa.Column("amount_min", sa.Integer(), nullable=True),
        sa.Column("amount_max", sa.Integer(), nullable=True),
        sa.Column("amount_text", sa.String(length=300), nullable=True),
        sa.Column("mechanism", sa.String(length=160), nullable=True),
        sa.Column("effort_index", sa.String(length=40), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("effort_score", sa.Float(), nullable=True),
        sa.Column("effort_confidence", sa.Float(), nullable=True),
        sa.Column("effort_rationale", sa.Text(), nullable=True),
        sa.Column("effort_signals_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("effort_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_public", sa.Text(), nullable=True),
        sa.Column("summary_private", sa.Text(), nullable=True),
        sa.Column("eligibility_summary", sa.Text(), nullable=True),
        sa.Column("notes_private", sa.Text(), nullable=True),
        sa.Column("topic_tags_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("method_tags_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("hub_relevance_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("raw_text_hash", sa.String(length=64), nullable=True),
        sa.Column("synthesized_json", sa.JSON(), nullable=True),
        sa.Column("synthesis_status", sa.String(length=40), nullable=False, server_default=sa.text("'not_started'")),
        sa.Column("synthesis_provider", sa.String(length=40), nullable=True),
        sa.Column("synthesis_model", sa.String(length=120), nullable=True),
        sa.Column("synthesis_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("synthesis_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synthesis_confidence", sa.Float(), nullable=True),
        sa.Column("synthesis_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'expired', 'archived')",
            name="ck_funding_opportunity_status",
        ),
        sa.CheckConstraint(
            "source_type IN ('manual', 'csv', 'imported', 'url_fetch', 'fetched_url', 'rss', 'public_search')",
            name="ck_funding_opportunity_source_type",
        ),
        sa.CheckConstraint(
            "effort_index IN ('mild', 'moderate', 'heavy', 'unknown')",
            name="ck_funding_opportunity_effort_index",
        ),
        sa.CheckConstraint(
            "synthesis_status IN ('not_started', 'fetched', 'synthesized', 'failed', 'needs_review')",
            name="ck_funding_opportunity_synthesis_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name="uq_funding_opportunity_external_id"),
        sa.UniqueConstraint("normalized_source_url", name="uq_funding_opportunity_normalized_source_url"),
        sa.UniqueConstraint("slug", name="uq_funding_opportunity_slug"),
    )
    op.create_index("ix_funding_opportunity_status_updated", "funding_opportunity", ["status", "updated_at"])
    op.create_index("ix_funding_opportunity_public_status", "funding_opportunity", ["is_public", "status"])
    op.create_index("ix_funding_opportunity_reviewed", "funding_opportunity", ["is_reviewed"])
    op.create_index("ix_funding_opportunity_deadline_date", "funding_opportunity", ["deadline_date"])
    op.create_index("ix_funding_opportunity_effort_index", "funding_opportunity", ["effort_index"])
    op.create_index("ix_funding_opportunity_raw_text_hash", "funding_opportunity", ["raw_text_hash"])


def downgrade():
    op.drop_index("ix_funding_opportunity_raw_text_hash", table_name="funding_opportunity")
    op.drop_index("ix_funding_opportunity_effort_index", table_name="funding_opportunity")
    op.drop_index("ix_funding_opportunity_deadline_date", table_name="funding_opportunity")
    op.drop_index("ix_funding_opportunity_reviewed", table_name="funding_opportunity")
    op.drop_index("ix_funding_opportunity_public_status", table_name="funding_opportunity")
    op.drop_index("ix_funding_opportunity_status_updated", table_name="funding_opportunity")
    op.drop_table("funding_opportunity")
