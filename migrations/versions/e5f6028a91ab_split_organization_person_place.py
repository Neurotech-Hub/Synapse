"""Split entity into organization, person, place; XOR source owner; persona_snapshot; polymorphic leads.

Revision ID: e5f6028a91ab
Revises: f4a9b1c8d_source_label

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5f6028a91ab"
down_revision = "f4a9b1c8d_source_label"
branch_labels = None
depends_on = None


def _columns(inspector: sa.Inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def _table_exists(inspector: sa.Inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if _table_exists(insp, "organization"):
        return

    op.create_table(
        "organization",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=512), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "person",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=512), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("institution", sa.String(length=512), nullable=True),
        sa.Column("department", sa.String(length=512), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "place",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=512), nullable=False),
        sa.Column("place_name", sa.String(length=512), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "persona_snapshot",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("place_id", sa.Integer(), nullable=True),
        sa.Column("research_focus", sa.JSON(), nullable=False),
        sa.Column("methods", sa.JSON(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("current_projects", sa.JSON(), nullable=False),
        sa.Column("funding_signals", sa.JSON(), nullable=False),
        sa.Column("collab_openness_score", sa.Float(), nullable=True),
        sa.Column("paper_count_last_90d", sa.Integer(), nullable=False),
        sa.Column("raw_papers_snapshot", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sources_last_scanned", sa.JSON(), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("input_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("build_status", sa.String(length=32), nullable=False),
        sa.Column("build_error", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(person_id IS NOT NULL AND organization_id IS NULL AND place_id IS NULL) OR "
            "(person_id IS NULL AND organization_id IS NOT NULL AND place_id IS NULL) OR "
            "(person_id IS NULL AND organization_id IS NULL AND place_id IS NOT NULL)",
            name="ck_persona_snapshot_subject_xor",
        ),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["place_id"], ["place.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_id"),
        sa.UniqueConstraint("organization_id"),
        sa.UniqueConstraint("place_id"),
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO organization (id, slug, display_name, notes, created_at)
            SELECT id, slug, display_name, notes, created_at FROM entity WHERE kind IN ('org', 'lab')
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO person (id, slug, display_name, notes, institution, department, organization_id, created_at)
            SELECT id, slug, display_name, notes, institution, department, NULL, created_at
            FROM entity WHERE kind = 'person'
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO place (id, slug, display_name, place_name, latitude, longitude, notes, organization_id, created_at)
            SELECT id, slug, display_name, display_name, 0.0, 0.0, notes, NULL, created_at
            FROM entity WHERE kind = 'place'
            """
        )
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO persona_snapshot (
                person_id, organization_id, place_id,
                research_focus, methods, keywords, current_projects, funding_signals,
                collab_openness_score, paper_count_last_90d, raw_papers_snapshot, notes,
                sources_last_scanned, prompt_version, model_used, input_fingerprint,
                build_status, build_error, generated_at, created_at, updated_at
            )
            SELECT
                CASE WHEN ent.kind = 'person' THEN ei.entity_id END,
                CASE WHEN ent.kind IN ('org', 'lab') THEN ei.entity_id END,
                CASE WHEN ent.kind = 'place' THEN ei.entity_id END,
                ei.research_focus, ei.methods, ei.keywords, ei.current_projects, ei.funding_signals,
                ei.collab_openness_score, ei.paper_count_last_90d, ei.raw_papers_snapshot, ei.notes,
                ei.sources_last_scanned, ei.prompt_version, ei.model_used, ei.input_fingerprint,
                ei.build_status, ei.build_error, ei.generated_at, ei.created_at, ei.updated_at
            FROM entity_identity ei JOIN entity ent ON ent.id = ei.entity_id
            """
        )
    )

    with op.batch_alter_table("source", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ownership_hint", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("person_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))

    conn.execute(
        sa.text(
            """
            UPDATE source SET organization_id = (
                SELECT se.entity_id FROM source_entity se
                JOIN entity e ON e.id = se.entity_id
                WHERE se.source_id = source.id AND e.kind IN ('org', 'lab')
                ORDER BY e.id ASC LIMIT 1
            )
            WHERE EXISTS (
                SELECT 1 FROM source_entity se JOIN entity e ON e.id = se.entity_id
                WHERE se.source_id = source.id AND e.kind IN ('org', 'lab')
            )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE source SET person_id = (
                SELECT se.entity_id FROM source_entity se
                JOIN entity e ON e.id = se.entity_id
                WHERE se.source_id = source.id AND e.kind = 'person'
                ORDER BY e.id ASC LIMIT 1
            )
            WHERE EXISTS (
                SELECT 1 FROM source_entity se JOIN entity e ON e.id = se.entity_id
                WHERE se.source_id = source.id AND e.kind = 'person'
            )
            """
        )
    )
    conn.execute(
        sa.text("UPDATE source SET organization_id = NULL WHERE person_id IS NOT NULL AND organization_id IS NOT NULL")
    )

    with op.batch_alter_table("source", schema=None) as batch_op:
        batch_op.create_foreign_key("fk_source_person_id", "person", ["person_id"], ["id"], ondelete="SET NULL")
        batch_op.create_foreign_key(
            "fk_source_organization_id", "organization", ["organization_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_check_constraint(
            "ck_source_person_org_xor_null",
            "(person_id IS NULL OR organization_id IS NULL)",
        )

    conn.execute(sa.text("DROP INDEX IF EXISTS uq_lead_entity_subject_fp"))

    with op.batch_alter_table("lead_candidate", schema=None) as batch_op:
        batch_op.add_column(sa.Column("target_person_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("target_organization_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("target_place_id", sa.Integer(), nullable=True))

    conn.execute(sa.text("UPDATE lead_candidate SET target_person_id = entity_id WHERE entity_id IN (SELECT id FROM person)"))
    conn.execute(
        sa.text("UPDATE lead_candidate SET target_organization_id = entity_id WHERE entity_id IN (SELECT id FROM organization)")
    )
    conn.execute(sa.text("UPDATE lead_candidate SET target_place_id = entity_id WHERE entity_id IN (SELECT id FROM place)"))

    insp_lc = sa.inspect(conn)
    entity_fk_names = [
        fk.get("name")
        for fk in insp_lc.get_foreign_keys("lead_candidate")
        if fk.get("referred_table") == "entity" and fk.get("constrained_columns") == ["entity_id"]
        and fk.get("name")
    ]
    with op.batch_alter_table("lead_candidate", schema=None) as batch_op:
        for cname in entity_fk_names:
            batch_op.drop_constraint(cname, type_="foreignkey")
        batch_op.drop_column("entity_id")
        batch_op.create_foreign_key("fk_lc_target_person", "person", ["target_person_id"], ["id"], ondelete="SET NULL")
        batch_op.create_foreign_key(
            "fk_lc_target_organization", "organization", ["target_organization_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_foreign_key("fk_lc_target_place", "place", ["target_place_id"], ["id"], ondelete="SET NULL")
        batch_op.create_check_constraint(
            "ck_lead_candidate_target_xor",
            "(CASE WHEN target_person_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN target_organization_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN target_place_id IS NOT NULL THEN 1 ELSE 0 END) <= 1",
        )

    with op.batch_alter_table("lead_pipeline_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hub_organization_id", sa.Integer(), nullable=True))

    conn.execute(
        sa.text(
            """
            UPDATE lead_pipeline_settings
            SET hub_organization_id = hub_program_entity_id
            WHERE hub_program_entity_id IS NOT NULL
              AND hub_program_entity_id IN (SELECT id FROM organization)
            """
        )
    )

    insp3 = sa.inspect(conn)
    lps_cols = _columns(insp3, "lead_pipeline_settings")
    lps_fks2 = [c["name"] for c in insp3.get_foreign_keys("lead_pipeline_settings")]

    with op.batch_alter_table("lead_pipeline_settings", schema=None) as batch_op:
        if "fk_lead_pipeline_hub_program_entity" in lps_fks2:
            batch_op.drop_constraint("fk_lead_pipeline_hub_program_entity", type_="foreignkey")
        elif "lead_pipeline_settings_ibfk_1" in lps_fks2:
            batch_op.drop_constraint("lead_pipeline_settings_ibfk_1", type_="foreignkey")
        if "hub_program_entity_id" in lps_cols:
            batch_op.drop_column("hub_program_entity_id")
        batch_op.create_foreign_key(
            "fk_lead_pipeline_hub_organization",
            "organization",
            ["hub_organization_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.drop_table("source_entity")
    op.drop_table("entity_identity")
    op.drop_table("entity")


def downgrade():
    raise NotImplementedError("Irreversible migration: entity model removed.")
