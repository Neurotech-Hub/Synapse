"""Drop source.label (unused display field).

Revision ID: b2c4_drop_source_label
Revises: d1e2f3a71528

"""

import sqlalchemy as sa
from alembic import op

revision = "b2c4_drop_source_label"
down_revision = "d1e2f3a71528"
branch_labels = None
depends_on = None


def _columns(inspector: sa.Inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "label" not in _columns(insp, "source"):
        return
    with op.batch_alter_table("source", schema=None) as batch_op:
        batch_op.drop_column("label")


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "label" in _columns(insp, "source"):
        return
    with op.batch_alter_table("source", schema=None) as batch_op:
        batch_op.add_column(sa.Column("label", sa.String(length=512), nullable=True))

