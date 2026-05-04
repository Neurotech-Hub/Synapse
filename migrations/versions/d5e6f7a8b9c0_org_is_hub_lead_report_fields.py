"""Add Organization.is_hub and LeadReport rich scoring fields.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-05-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("organization", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_hub", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table("lead_report", schema=None) as batch_op:
        batch_op.add_column(sa.Column("fit_score", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("email_draft", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("positive_signals", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("uncertainties", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("likely_technical_pain", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("lead_report", schema=None) as batch_op:
        batch_op.drop_column("likely_technical_pain")
        batch_op.drop_column("uncertainties")
        batch_op.drop_column("positive_signals")
        batch_op.drop_column("email_draft")
        batch_op.drop_column("fit_score")

    with op.batch_alter_table("organization", schema=None) as batch_op:
        batch_op.drop_column("is_hub")
