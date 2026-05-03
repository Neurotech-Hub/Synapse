"""lead_pipeline_settings singleton for admin pipeline toggles

Revision ID: c7e22aa1b04d
Revises: f3a9012b6c41
Create Date: 2026-05-02

"""

import sqlalchemy as sa
from alembic import op

revision = "c7e22aa1b04d"
down_revision = "f3a9012b6c41"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lead_pipeline_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("qualify_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("prompt_version", sa.String(length=64), nullable=False, server_default="1"),
        sa.Column("max_hub_items", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("max_candidates_per_run", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("entity_catalog_max", sa.Integer(), nullable=False, server_default="40"),
        sa.PrimaryKeyConstraint("id"),
    )
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO lead_pipeline_settings "
            "(id, qualify_enabled, prompt_version, max_hub_items, max_candidates_per_run, entity_catalog_max) "
            "VALUES (1, 0, '1', 25, 30, 40)"
        )
    )


def downgrade():
    op.drop_table("lead_pipeline_settings")
