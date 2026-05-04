"""Drop lead_pipeline_settings table; auto-migrate hub_organization_id to Organization.is_hub.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-05-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    try:
        row = conn.execute(
            sa.text("SELECT hub_organization_id FROM lead_pipeline_settings WHERE id = 1")
        ).fetchone()
        if row and row[0]:
            conn.execute(
                sa.text("UPDATE organization SET is_hub = 1 WHERE id = :oid"),
                {"oid": row[0]},
            )
    except Exception:
        pass
    op.drop_table("lead_pipeline_settings")


def downgrade():
    op.create_table(
        "lead_pipeline_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hub_organization_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["hub_organization_id"],
            ["organization.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
