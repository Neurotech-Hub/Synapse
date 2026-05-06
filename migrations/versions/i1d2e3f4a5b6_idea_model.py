"""add idea table

Revision ID: i1d2e3f4a5b6
Revises: h1c2d3e4f5a6
Create Date: 2026-05-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "i1d2e3f4a5b6"
down_revision = "h1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "idea",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("slug", sa.String(length=260), nullable=False),
        sa.Column("idea_type", sa.String(length=50), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_reviewed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("short_description", sa.String(length=500), nullable=True),
        sa.Column("public_summary", sa.Text(), nullable=True),
        sa.Column("private_summary", sa.Text(), nullable=True),
        sa.Column("hub_relevance", sa.Text(), nullable=True),
        sa.Column("buildable_angle", sa.Text(), nullable=True),
        sa.Column("funding_angle", sa.Text(), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("aliases_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("hub_capabilities_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("evidence_refs_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("synthesized_json", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("quality_flags_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_by", sa.String(length=80), nullable=True),
        sa.Column("created_via", sa.String(length=40), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
            "idea_type IN ("
            "'research_theme', 'technical_capability', 'buildable_concept', 'method_cluster', "
            "'funding_theme', 'strategic_area', 'public_resource_topic', 'unknown'"
            ")",
            name="ck_idea_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'review', 'public', 'private', 'archived', 'hidden', 'merged')",
            name="ck_idea_status",
        ),
        sa.CheckConstraint(
            "created_via IN ('manual', 'persona_extract', 'content_extract', 'funding_extract', 'admin_seed', 'imported')",
            name="ck_idea_created_via",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_idea_slug"),
    )
    op.create_index("ix_idea_status_updated", "idea", ["status", "updated_at"])
    op.create_index("ix_idea_public_status", "idea", ["is_public", "status"])
    op.create_index("ix_idea_type", "idea", ["idea_type"])
    op.create_index("ix_idea_reviewed", "idea", ["is_reviewed"])
    op.create_index("ix_idea_created_via", "idea", ["created_via"])


def downgrade():
    op.drop_index("ix_idea_created_via", table_name="idea")
    op.drop_index("ix_idea_reviewed", table_name="idea")
    op.drop_index("ix_idea_type", table_name="idea")
    op.drop_index("ix_idea_public_status", table_name="idea")
    op.drop_index("ix_idea_status_updated", table_name="idea")
    op.drop_table("idea")
