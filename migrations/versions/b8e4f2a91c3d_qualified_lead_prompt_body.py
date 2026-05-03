"""lead_pipeline_settings: optional DB-backed qualified lead prompt body

Revision ID: b8e4f2a91c3d
Revises: c7e22aa1b04d
Create Date: 2026-05-02

"""

import sqlalchemy as sa
from alembic import op

revision = "b8e4f2a91c3d"
down_revision = "c7e22aa1b04d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "lead_pipeline_settings",
        sa.Column("qualified_lead_prompt_body", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("lead_pipeline_settings", "qualified_lead_prompt_body")
