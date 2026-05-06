"""Add Source.last_poll_at for public latest metadata.

Revision ID: f1a2b3c4d5e6
Revises: e6f7a8b9c0d1
Create Date: 2026-05-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("source", schema=None) as batch_op:
        batch_op.add_column(sa.Column("last_poll_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("source", schema=None) as batch_op:
        batch_op.drop_column("last_poll_at")
