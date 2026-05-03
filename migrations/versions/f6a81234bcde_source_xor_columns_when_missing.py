"""Ensure source XOR columns exist if e5f6028a91ab exited early.

Revision ID: f6a81234bcde
Revises: e5f6028a91ab

The split migration returns immediately when ``organization`` already exists
(e.g. schema created via ``db.create_all()``). That skipped adding ``ownership_hint``,
``person_id``, and ``organization_id`` on ``source``. This revision backfills safely.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6a81234bcde"
down_revision = "e5f6028a91ab"
branch_labels = None
depends_on = None


def _columns(inspector: sa.Inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def _table_exists(inspector: sa.Inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _fk_by_constrained(inspector: sa.Inspector, table: str) -> dict[str, tuple[str | None, str | None]]:
    """Map constrained column -> (referred_table, constraint_name)."""

    out: dict[str, tuple[str | None, str | None]] = {}
    for fk in inspector.get_foreign_keys(table):
        rt = fk.get("referred_table")
        nm = fk.get("name")
        for col in fk.get("constrained_columns") or []:
            out[col] = (rt, nm)
    return out


def _check_constraint_names(inspector: sa.Inspector, table: str) -> set[str]:
    names: set[str] = set()
    for c in inspector.get_check_constraints(table):
        n = c.get("name")
        if n:
            names.add(n)
    return names


def _source_has_person_org_xor_check(inspector: sa.Inspector) -> bool:
    """Detect an XOR-style check even when SQLite omits a stable name."""

    for c in inspector.get_check_constraints("source"):
        st = (c.get("sqltext") or "").upper()
        if "PERSON_ID" in st and "ORGANIZATION_ID" in st and "NULL" in st:
            return True
    return False


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not _table_exists(insp, "source"):
        return

    cols = _columns(insp, "source")
    with op.batch_alter_table("source", schema=None) as batch_op:
        if "ownership_hint" not in cols:
            batch_op.add_column(sa.Column("ownership_hint", sa.String(length=32), nullable=True))
        if "person_id" not in cols:
            batch_op.add_column(sa.Column("person_id", sa.Integer(), nullable=True))
        if "organization_id" not in cols:
            batch_op.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))

    insp = sa.inspect(conn)
    cols = _columns(insp, "source")
    fkc = _fk_by_constrained(insp, "source")
    chk = _check_constraint_names(insp, "source")
    has_xor_check = "ck_source_person_org_xor_null" in chk or _source_has_person_org_xor_check(insp)

    with op.batch_alter_table("source", schema=None) as batch_op:
        if "person_id" in cols and _table_exists(insp, "person"):
            rt, _ = fkc.get("person_id", (None, None))
            if rt != "person":
                batch_op.create_foreign_key(
                    "fk_source_person_id",
                    "person",
                    ["person_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
        if "organization_id" in cols and _table_exists(insp, "organization"):
            rt, _ = fkc.get("organization_id", (None, None))
            if rt != "organization":
                batch_op.create_foreign_key(
                    "fk_source_organization_id",
                    "organization",
                    ["organization_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
        if "person_id" in cols and "organization_id" in cols and not has_xor_check:
            batch_op.create_check_constraint(
                "ck_source_person_org_xor_null",
                "(person_id IS NULL OR organization_id IS NULL)",
            )


def downgrade():
    pass
