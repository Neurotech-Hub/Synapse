"""Many-to-many person↔organization and organization↔place (drop single FK columns).

Revision ID: d7e833f90412
Revises: c1d2e3f405ab

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d7e833f90412"
down_revision = "c1d2e3f405ab"
branch_labels = None
depends_on = None


def _columns(inspector: sa.Inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = insp.get_table_names()

    if "person_organization" not in tables:
        op.create_table(
            "person_organization",
            sa.Column("person_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["person_id"], ["person.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("person_id", "organization_id"),
        )

    if "organization_place" not in tables:
        op.create_table(
            "organization_place",
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("place_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["place_id"], ["place.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("organization_id", "place_id"),
        )

    if "person" in tables and "organization_id" in _columns(insp, "person"):
        op.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO person_organization (person_id, organization_id)
                SELECT id, organization_id FROM person WHERE organization_id IS NOT NULL
                """
            )
        )
        with op.batch_alter_table("person", schema=None) as batch_op:
            batch_op.drop_column("organization_id")

    if "place" in tables and "organization_id" in _columns(insp, "place"):
        op.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO organization_place (organization_id, place_id)
                SELECT organization_id, id FROM place WHERE organization_id IS NOT NULL
                """
            )
        )
        with op.batch_alter_table("place", schema=None) as batch_op:
            batch_op.drop_column("organization_id")


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = insp.get_table_names()

    if "place" in tables:
        cols = _columns(insp, "place")
        if "organization_id" not in cols:
            with op.batch_alter_table("place", schema=None) as batch_op:
                batch_op.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))
            if "organization_place" in tables:
                op.execute(
                    sa.text(
                        """
                        UPDATE place SET organization_id = (
                            SELECT organization_id FROM organization_place
                            WHERE organization_place.place_id = place.id LIMIT 1
                        )
                        """
                    )
                )

    if "person" in tables:
        cols = _columns(insp, "person")
        if "organization_id" not in cols:
            with op.batch_alter_table("person", schema=None) as batch_op:
                batch_op.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))
            if "person_organization" in tables:
                op.execute(
                    sa.text(
                        """
                        UPDATE person SET organization_id = (
                            SELECT organization_id FROM person_organization
                            WHERE person_organization.person_id = person.id LIMIT 1
                        )
                        """
                    )
                )

    if "organization_place" in tables:
        op.drop_table("organization_place")
    if "person_organization" in tables:
        op.drop_table("person_organization")
