"""Drop source.lead_source (Hub membership is Hub program entity tag on source).

Revision ID: c9d8e7152426
Revises: a1c2d3e4f5a6

"""

import sqlalchemy as sa
from alembic import op

revision = "c9d8e7152426"
down_revision = "a1c2d3e4f5a6"
branch_labels = None
depends_on = None


def _columns(inspector: sa.Inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "lead_source" not in _columns(insp, "source"):
        return
    with op.batch_alter_table("source", schema=None) as batch_op:
        batch_op.drop_column("lead_source")


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "lead_source" in _columns(insp, "source"):
        return
    with op.batch_alter_table("source", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("lead_source", sa.Boolean(), nullable=False, server_default=sa.false())
        )
