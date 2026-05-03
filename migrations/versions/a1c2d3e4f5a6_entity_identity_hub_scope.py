"""entity identity (PIPersona-shaped), entity affiliation, hub corpus link, program entity

Revision ID: a1c2d3e4f5a6
Revises: b8e4f2a91c3d
Create Date: 2026-05-02

"""

import sqlalchemy as sa
from alembic import op

revision = "a1c2d3e4f5a6"
down_revision = "b8e4f2a91c3d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("entity", sa.Column("institution", sa.String(length=512), nullable=True))
    op.add_column("entity", sa.Column("department", sa.String(length=512), nullable=True))
    with op.batch_alter_table("source_entity", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("feeds_hub_corpus", sa.Boolean(), nullable=False, server_default=sa.true())
        )

    with op.batch_alter_table("lead_pipeline_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hub_program_entity_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_lead_pipeline_hub_program_entity",
            "entity",
            ["hub_program_entity_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "entity_identity",
        sa.Column("entity_id", sa.Integer(), nullable=False),
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["entity.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("entity_id"),
    )


def downgrade():
    op.drop_table("entity_identity")

    with op.batch_alter_table("lead_pipeline_settings", schema=None) as batch_op:
        batch_op.drop_constraint("fk_lead_pipeline_hub_program_entity", type_="foreignkey")
        batch_op.drop_column("hub_program_entity_id")

    with op.batch_alter_table("source_entity", schema=None) as batch_op:
        batch_op.drop_column("feeds_hub_corpus")

    op.drop_column("entity", "department")
    op.drop_column("entity", "institution")
