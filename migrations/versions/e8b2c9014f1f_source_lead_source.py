"""source lead_source flag

Revision ID: e8b2c9014f1f
Revises: d4dc78c262ad
Create Date: 2026-05-03

"""

import sqlalchemy as sa
from alembic import op

revision = "e8b2c9014f1f"
down_revision = "d4dc78c262ad"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "source",
        sa.Column(
            "lead_source",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_column("source", "lead_source")
