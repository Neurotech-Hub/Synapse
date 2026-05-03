"""Remove legacy lead_candidate watermark and slim lead_pipeline_settings.

Revision ID: b3c4d5e6f708
Revises: f2c3b4d5e6f7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b3c4d5e6f708"
down_revision = "f2c3b4d5e6f7"
branch_labels = None
depends_on = None


def _table_columns(conn: sa.engine.Connection, table: str) -> set[str]:
    insp = sa.inspect(conn)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = set(insp.get_table_names())

    if "lead_candidate" in tables:
        op.drop_table("lead_candidate")
    if "lead_gen_watermark" in tables:
        op.drop_table("lead_gen_watermark")

    cols = _table_columns(conn, "lead_pipeline_settings")
    drop_cols = (
        "qualify_enabled",
        "prompt_version",
        "qualified_lead_prompt_body",
        "max_hub_items",
        "max_candidates_per_run",
        "entity_catalog_max",
    )
    with op.batch_alter_table("lead_pipeline_settings") as batch_op:
        for c in drop_cols:
            if c in cols:
                batch_op.drop_column(c)


def downgrade():
    raise NotImplementedError("Legacy lead_candidate / watermark intentionally removed.")
