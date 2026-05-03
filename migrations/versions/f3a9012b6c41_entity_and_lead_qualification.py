"""entity source associations lead qualification fields watermark

Revision ID: f3a9012b6c41
Revises: e8b2c9014f1f
Create Date: 2026-05-03

"""

import sqlalchemy as sa
from alembic import op

revision = "f3a9012b6c41"
down_revision = "e8b2c9014f1f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "entity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=512), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_entity_slug"),
    )
    op.create_table(
        "source_entity",
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entity.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["source.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id", "entity_id"),
    )
    op.create_table(
        "lead_gen_watermark",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("last_candidate_content_item_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", name="uq_lead_gen_watermark_scope"),
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO lead_gen_watermark (id, scope, last_candidate_content_item_id) "
            "VALUES (1, 'global', NULL)"
        )
    )

    with op.batch_alter_table("lead_candidate", schema=None) as batch_op:
        batch_op.add_column(sa.Column("anchor_hub_content_item_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("hub_cited_content_item_ids", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("hub_context_hash", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("prompt_version", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("entity_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("subject_fingerprint", sa.String(length=512), nullable=True))
        batch_op.create_foreign_key(
            "fk_lead_candidate_anchor_hub",
            "content_item",
            ["anchor_hub_content_item_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_lead_candidate_entity",
            "entity",
            ["entity_id"],
            ["id"],
            ondelete="SET NULL",
        )

    conn.execute(
        sa.text(
            "UPDATE lead_candidate SET prompt_version = 'legacy', "
            "hub_context_hash = 'legacy-' || CAST(id AS TEXT) "
            "WHERE hub_context_hash IS NULL OR prompt_version IS NULL"
        )
    )

    with op.batch_alter_table("lead_candidate", schema=None) as batch_op:
        batch_op.alter_column(
            "hub_context_hash",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        batch_op.alter_column(
            "prompt_version",
            existing_type=sa.String(length=64),
            nullable=False,
        )

    op.create_index(
        "uq_lead_qual_candidate_prompt_hash",
        "lead_candidate",
        ["content_item_id", "prompt_version", "hub_context_hash"],
        unique=True,
    )

    conn.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_lead_entity_subject_fp
            ON lead_candidate (entity_id, subject_fingerprint)
            WHERE entity_id IS NOT NULL
              AND subject_fingerprint IS NOT NULL
              AND subject_fingerprint != ''
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS uq_lead_entity_subject_fp"))
    op.drop_index("uq_lead_qual_candidate_prompt_hash", table_name="lead_candidate")

    with op.batch_alter_table("lead_candidate", schema=None) as batch_op:
        batch_op.drop_constraint("fk_lead_candidate_anchor_hub", type_="foreignkey")
        batch_op.drop_constraint("fk_lead_candidate_entity", type_="foreignkey")
        batch_op.drop_column("subject_fingerprint")
        batch_op.drop_column("entity_id")
        batch_op.drop_column("prompt_version")
        batch_op.drop_column("hub_context_hash")
        batch_op.drop_column("hub_cited_content_item_ids")
        batch_op.drop_column("anchor_hub_content_item_id")

    op.drop_table("lead_gen_watermark")
    op.drop_table("source_entity")
    op.drop_table("entity")
