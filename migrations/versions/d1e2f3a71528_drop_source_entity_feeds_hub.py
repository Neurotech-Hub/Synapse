"""Drop source_entity.feeds_hub_corpus (Hub = tag Hub program entity on source).

Revision ID: d1e2f3a71528
Revises: c9d8e7152426

"""

import sqlalchemy as sa
from alembic import op

revision = "d1e2f3a71528"
down_revision = "c9d8e7152426"
branch_labels = None
depends_on = None


def _columns(inspector: sa.Inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "feeds_hub_corpus" not in _columns(insp, "source_entity"):
        return
    with op.batch_alter_table("source_entity", schema=None) as batch_op:
        batch_op.drop_column("feeds_hub_corpus")


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "feeds_hub_corpus" in _columns(insp, "source_entity"):
        return
    with op.batch_alter_table("source_entity", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("feeds_hub_corpus", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
