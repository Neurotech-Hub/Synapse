"""add idea suggestions

Revision ID: m1b2c3d4e5f6
Revises: l1a2b3c4d5e6
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "m1b2c3d4e5f6"
down_revision = "l1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "idea_suggestion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("idea_type", sa.String(length=50), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("short_description", sa.String(length=500), nullable=True),
        sa.Column("public_summary", sa.Text(), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("aliases_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("hub_capabilities_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("evidence_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("duplicate_candidate_id", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("llm_run_id", sa.Integer(), nullable=True),
        sa.Column("accepted_idea_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(datetime('now'))")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source_type IN ('persona_snapshot', 'content_item', 'person', 'organization', 'building', 'region')",
            name="ck_idea_suggestion_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'merged')",
            name="ck_idea_suggestion_status",
        ),
        sa.ForeignKeyConstraint(["accepted_idea_id"], ["idea.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["duplicate_candidate_id"], ["idea.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["llm_run_id"], ["llm_run.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_idea_suggestion_status_created", "idea_suggestion", ["status", "created_at"])
    op.create_index("ix_idea_suggestion_source", "idea_suggestion", ["source_type", "source_id"])


def downgrade():
    op.drop_index("ix_idea_suggestion_source", table_name="idea_suggestion")
    op.drop_index("ix_idea_suggestion_status_created", table_name="idea_suggestion")
    op.drop_table("idea_suggestion")
