"""add idea suggestion duplicate metadata

Revision ID: n1c2d3e4f5a6
Revises: m1b2c3d4e5f6
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "n1c2d3e4f5a6"
down_revision = "m1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade():
    existing = _columns("idea_suggestion")
    with op.batch_alter_table("idea_suggestion", schema=None) as batch_op:
        if "duplicate_reason" not in existing:
            batch_op.add_column(sa.Column("duplicate_reason", sa.Text(), nullable=True))
        if "duplicate_confidence" not in existing:
            batch_op.add_column(sa.Column("duplicate_confidence", sa.Float(), nullable=True))


def downgrade():
    existing = _columns("idea_suggestion")
    with op.batch_alter_table("idea_suggestion", schema=None) as batch_op:
        if "duplicate_confidence" in existing:
            batch_op.drop_column("duplicate_confidence")
        if "duplicate_reason" in existing:
            batch_op.drop_column("duplicate_reason")
