"""Drop redundant region.display_name (slug derives from region_name).

Revision ID: 2b3c4d5e6f70
Revises: f9a8b7c6d5e4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "2b3c4d5e6f70"
down_revision = "f9a8b7c6d5e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("region", recreate="always") as batch:
            batch.drop_column("display_name")
    else:
        op.drop_column("region", "display_name")


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("region", recreate="always") as batch:
            batch.add_column(sa.Column("display_name", sa.String(length=512), nullable=True))
    else:
        op.add_column("region", sa.Column("display_name", sa.String(length=512), nullable=True))
    op.execute(sa.text("UPDATE region SET display_name = region_name WHERE display_name IS NULL"))
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("region", recreate="always") as batch:
            batch.alter_column(
                "display_name",
                existing_type=sa.String(length=512),
                nullable=False,
            )
    else:
        op.alter_column(
            "region",
            "display_name",
            existing_type=sa.String(length=512),
            nullable=False,
        )
