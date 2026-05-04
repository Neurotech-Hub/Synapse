"""Public activity digest + per-entity stale flags.

Revision ID: c8d9e0f1a2b3
Revises: b3c4d5e6f708
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c8d9e0f1a2b3"
down_revision = "b3c4d5e6f708"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "person",
        sa.Column("public_digest_stale", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "organization",
        sa.Column("public_digest_stale", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_table(
        "public_activity_digest",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("cited_content_item_ids_json", sa.Text(), nullable=True),
        sa.Column("input_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=False, server_default="1"),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'ok'")),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(CASE WHEN person_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN organization_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_public_activity_digest_target_one",
        ),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pad_person_created", "public_activity_digest", ["person_id", "created_at"])
    op.create_index("ix_pad_org_created", "public_activity_digest", ["organization_id", "created_at"])


def downgrade():
    op.drop_index("ix_pad_org_created", table_name="public_activity_digest")
    op.drop_index("ix_pad_person_created", table_name="public_activity_digest")
    op.drop_table("public_activity_digest")
    op.drop_column("organization", "public_digest_stale")
    op.drop_column("person", "public_digest_stale")
