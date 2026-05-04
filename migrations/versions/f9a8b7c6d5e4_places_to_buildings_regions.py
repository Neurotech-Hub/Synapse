"""Places pivot: building table, region, org.building_id, region_building, lead_report building/region targets.

Revision ID: f9a8b7c6d5e4
Revises: e3f4a5b6c7d8
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f9a8b7c6d5e4"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def _table_cols(conn, table: str) -> set[str]:
    try:
        return {c["name"] for c in sa.inspect(conn).get_columns(table)}
    except sa.exc.NoSuchTableError:
        return set()


def _drop_fk_by_ref(conn, table: str, referred_table: str, cols: list[str]) -> None:
    """Drop FK by referred table (Postgres and others). SQLite: skip — handled via batch_alter."""

    if conn.dialect.name == "sqlite":
        return
    for fk in sa.inspect(conn).get_foreign_keys(table):
        if fk.get("referred_table") == referred_table and list(fk.get("constrained_columns") or []) == cols:
            name = fk.get("name")
            if name:
                op.drop_constraint(name, table, type_="foreignkey")
            return


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name
    tables = set(sa.inspect(conn).get_table_names())

    if "building" in tables and "place" not in tables and "region_building" in tables:
        return

    created_at_srv = sa.text("(datetime('now'))") if dialect == "sqlite" else sa.text("now()")

    if "region" not in tables:
        op.create_table(
            "region",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("slug", sa.String(length=160), nullable=False),
            sa.Column("display_name", sa.String(length=512), nullable=False),
            sa.Column("region_name", sa.String(length=512), nullable=False),
            sa.Column("geojson", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=created_at_srv),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )

    org_cols = _table_cols(conn, "organization")
    if "building_id" not in org_cols:
        op.add_column("organization", sa.Column("building_id", sa.Integer(), nullable=True))

    if "organization_place" in tables:
        op.execute(
            sa.text(
                """
                UPDATE organization SET building_id = (
                    SELECT MIN(op.place_id) FROM organization_place op
                    WHERE op.organization_id = organization.id
                )
                WHERE EXISTS (
                    SELECT 1 FROM organization_place op2 WHERE op2.organization_id = organization.id
                )
                """
            )
        )
        op.drop_table("organization_place")

    if "place" in tables:
        _drop_fk_by_ref(conn, "persona_snapshot", "place", ["place_id"])
        _drop_fk_by_ref(conn, "lead_report", "place", ["target_place_id"])
        op.rename_table("place", "building")

    insp2 = sa.inspect(conn)
    org_has_bfk = any(
        fk.get("referred_table") == "building" and fk.get("constrained_columns") == ["building_id"]
        for fk in insp2.get_foreign_keys("organization")
    )
    if "building_id" in _table_cols(conn, "organization") and not org_has_bfk:
        if dialect == "sqlite":
            with op.batch_alter_table("organization", schema=None) as batch:
                batch.create_foreign_key(
                    "fk_organization_building_id",
                    "building",
                    ["building_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
        else:
            op.create_foreign_key(
                "fk_organization_building_id",
                "organization",
                "building",
                ["building_id"],
                ["id"],
                ondelete="SET NULL",
            )

    bcols = _table_cols(conn, "building")
    if "region_id" not in bcols:
        if dialect == "sqlite":
            with op.batch_alter_table("building", schema=None) as batch:
                batch.add_column(sa.Column("region_id", sa.Integer(), nullable=True))
                batch.create_foreign_key(
                    "fk_building_region_id",
                    "region",
                    ["region_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
        else:
            op.add_column("building", sa.Column("region_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_building_region_id",
                "building",
                "region",
                ["region_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if "region_building" not in set(sa.inspect(conn).get_table_names()):
        op.create_table(
            "region_building",
            sa.Column("region_id", sa.Integer(), nullable=False),
            sa.Column("building_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["region_id"], ["region.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["building_id"], ["building.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("region_id", "building_id"),
        )
        op.create_index("ix_region_building_region_id", "region_building", ["region_id"], unique=False)
        op.create_index("ix_region_building_building_id", "region_building", ["building_id"], unique=False)

    pcols = _table_cols(conn, "persona_snapshot")
    if "place_id" in pcols and "building_id" not in pcols:
        if dialect == "sqlite":
            with op.batch_alter_table("persona_snapshot", schema=None, recreate="always") as batch:
                batch.drop_constraint("ck_persona_snapshot_subject_xor", type_="check")
                batch.alter_column(
                    "place_id",
                    new_column_name="building_id",
                    existing_type=sa.Integer(),
                    type_=sa.Integer(),
                    nullable=True,
                )
                batch.create_foreign_key(
                    "fk_persona_snapshot_building_id",
                    "building",
                    ["building_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
                batch.create_check_constraint(
                    "ck_persona_snapshot_subject_xor",
                    "(person_id IS NOT NULL AND organization_id IS NULL AND building_id IS NULL) OR "
                    "(person_id IS NULL AND organization_id IS NOT NULL AND building_id IS NULL) OR "
                    "(person_id IS NULL AND organization_id IS NULL AND building_id IS NOT NULL)",
                )
        else:
            op.drop_constraint("ck_persona_snapshot_subject_xor", "persona_snapshot", type_="check")
            _drop_fk_by_ref(conn, "persona_snapshot", "place", ["place_id"])
            _drop_fk_by_ref(conn, "persona_snapshot", "building", ["place_id"])
            with op.batch_alter_table("persona_snapshot", schema=None) as batch:
                batch.alter_column(
                    "place_id",
                    new_column_name="building_id",
                    existing_type=sa.Integer(),
                    type_=sa.Integer(),
                    nullable=True,
                )
                batch.create_foreign_key(
                    "fk_persona_snapshot_building_id", "building", ["building_id"], ["id"], ondelete="CASCADE"
                )
            op.create_check_constraint(
                "ck_persona_snapshot_subject_xor",
                "persona_snapshot",
                "(person_id IS NOT NULL AND organization_id IS NULL AND building_id IS NULL) OR "
                "(person_id IS NULL AND organization_id IS NOT NULL AND building_id IS NULL) OR "
                "(person_id IS NULL AND organization_id IS NULL AND building_id IS NOT NULL)",
            )

    lcols = _table_cols(conn, "lead_report")
    if "target_place_id" in lcols:
        try:
            op.drop_index(op.f("ix_lead_report_target_place_id"), table_name="lead_report")
        except Exception:
            pass
        if dialect == "sqlite":
            with op.batch_alter_table("lead_report", schema=None, recreate="always") as batch:
                batch.drop_constraint("ck_lead_report_target_one", type_="check")
                batch.alter_column(
                    "target_place_id",
                    new_column_name="target_building_id",
                    existing_type=sa.Integer(),
                    type_=sa.Integer(),
                    nullable=True,
                )
                batch.create_foreign_key(
                    "fk_lead_report_target_building_id",
                    "building",
                    ["target_building_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
                batch.add_column(sa.Column("target_region_id", sa.Integer(), nullable=True))
                batch.create_foreign_key(
                    "fk_lead_report_target_region_id",
                    "region",
                    ["target_region_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
                batch.create_check_constraint(
                    "ck_lead_report_target_one",
                    "(CASE WHEN target_person_id IS NOT NULL THEN 1 ELSE 0 END + "
                    "CASE WHEN target_organization_id IS NOT NULL THEN 1 ELSE 0 END + "
                    "CASE WHEN target_building_id IS NOT NULL THEN 1 ELSE 0 END + "
                    "CASE WHEN target_region_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
                )
        else:
            op.drop_constraint("ck_lead_report_target_one", "lead_report", type_="check")
            _drop_fk_by_ref(conn, "lead_report", "place", ["target_place_id"])
            _drop_fk_by_ref(conn, "lead_report", "building", ["target_place_id"])
            with op.batch_alter_table("lead_report", schema=None) as batch:
                batch.alter_column(
                    "target_place_id",
                    new_column_name="target_building_id",
                    existing_type=sa.Integer(),
                    type_=sa.Integer(),
                    nullable=True,
                )
                batch.create_foreign_key(
                    "fk_lead_report_target_building_id",
                    "building",
                    ["target_building_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
                batch.add_column(sa.Column("target_region_id", sa.Integer(), nullable=True))
                batch.create_foreign_key(
                    "fk_lead_report_target_region_id",
                    "region",
                    ["target_region_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
            op.create_check_constraint(
                "ck_lead_report_target_one",
                "lead_report",
                "(CASE WHEN target_person_id IS NOT NULL THEN 1 ELSE 0 END + "
                "CASE WHEN target_organization_id IS NOT NULL THEN 1 ELSE 0 END + "
                "CASE WHEN target_building_id IS NOT NULL THEN 1 ELSE 0 END + "
                "CASE WHEN target_region_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            )
        op.create_index(op.f("ix_lead_report_target_building_id"), "lead_report", ["target_building_id"], unique=False)
        op.create_index(op.f("ix_lead_report_target_region_id"), "lead_report", ["target_region_id"], unique=False)


def downgrade():
    raise NotImplementedError("Downgrade not supported for this schema pivot.")
