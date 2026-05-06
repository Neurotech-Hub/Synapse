"""backfill funding effort columns for existing dev databases

Revision ID: k1f2a3b4c5d6
Revises: j1e2f3a4b5c6
Create Date: 2026-05-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "k1f2a3b4c5d6"
down_revision = "j1e2f3a4b5c6"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade():
    existing = _columns("funding_opportunity")
    with op.batch_alter_table("funding_opportunity", schema=None) as batch_op:
        if "effort_confidence" not in existing:
            batch_op.add_column(sa.Column("effort_confidence", sa.Float(), nullable=True))
        if "effort_signals_json" not in existing:
            batch_op.add_column(
                sa.Column("effort_signals_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
            )
        if "effort_reviewed_at" not in existing:
            batch_op.add_column(sa.Column("effort_reviewed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    existing = _columns("funding_opportunity")
    with op.batch_alter_table("funding_opportunity", schema=None) as batch_op:
        if "effort_reviewed_at" in existing:
            batch_op.drop_column("effort_reviewed_at")
        if "effort_signals_json" in existing:
            batch_op.drop_column("effort_signals_json")
        if "effort_confidence" in existing:
            batch_op.drop_column("effort_confidence")
