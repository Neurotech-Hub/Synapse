"""Drop person.institution and person.department (affiliation via organization only).

Revision ID: c1d2e3f405ab
Revises: f6a81234bcde

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c1d2e3f405ab"
down_revision = "f6a81234bcde"
branch_labels = None
depends_on = None


def _columns(inspector: sa.Inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "person" not in insp.get_table_names():
        return
    cols = _columns(insp, "person")
    with op.batch_alter_table("person", schema=None) as batch_op:
        if "institution" in cols:
            batch_op.drop_column("institution")
        if "department" in cols:
            batch_op.drop_column("department")


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "person" not in insp.get_table_names():
        return
    cols = _columns(insp, "person")
    with op.batch_alter_table("person", schema=None) as batch_op:
        if "institution" not in cols:
            batch_op.add_column(sa.Column("institution", sa.String(length=512), nullable=True))
        if "department" not in cols:
            batch_op.add_column(sa.Column("department", sa.String(length=512), nullable=True))
