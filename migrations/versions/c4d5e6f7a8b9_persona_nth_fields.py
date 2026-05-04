"""Add hardware_interests and infrastructure_needs to persona_snapshot.

Revision ID: c4d5e6f7a8b9
Revises: 2b3c4d5e6f70
Create Date: 2026-05-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "2b3c4d5e6f70"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("persona_snapshot", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hardware_interests", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("infrastructure_needs", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("persona_snapshot", schema=None) as batch_op:
        batch_op.drop_column("infrastructure_needs")
        batch_op.drop_column("hardware_interests")
