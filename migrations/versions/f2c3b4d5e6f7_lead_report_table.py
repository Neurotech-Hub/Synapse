"""Lead report hub-centric synthesis rows.

Revision ID: f2c3b4d5e6f7
Revises: d7e833f90412
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f2c3b4d5e6f7"
down_revision = "d7e833f90412"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lead_report",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hub_organization_id", sa.Integer(), nullable=True),
        sa.Column("target_person_id", sa.Integer(), nullable=True),
        sa.Column("target_organization_id", sa.Integer(), nullable=True),
        sa.Column("target_place_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default=sa.text("'queued'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executive_summary", sa.Text(), nullable=True),
        sa.Column("collaboration_routes_json", sa.Text(), nullable=True),
        sa.Column("ranked_contacts_json", sa.Text(), nullable=True),
        sa.Column("input_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(CASE WHEN target_person_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN target_organization_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN target_place_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_lead_report_target_one",
        ),
        sa.ForeignKeyConstraint(["hub_organization_id"], ["organization.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_person_id"], ["person.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_place_id"], ["place.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_report_hub_org_created", "lead_report", ["hub_organization_id", "created_at"])
    op.create_index("ix_lead_report_status_created", "lead_report", ["status", "created_at"])
    op.create_index(op.f("ix_lead_report_target_person_id"), "lead_report", ["target_person_id"], unique=False)
    op.create_index(
        op.f("ix_lead_report_target_organization_id"), "lead_report", ["target_organization_id"], unique=False
    )
    op.create_index(op.f("ix_lead_report_target_place_id"), "lead_report", ["target_place_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_lead_report_target_place_id"), table_name="lead_report")
    op.drop_index(op.f("ix_lead_report_target_organization_id"), table_name="lead_report")
    op.drop_index(op.f("ix_lead_report_target_person_id"), table_name="lead_report")
    op.drop_index("ix_lead_report_status_created", table_name="lead_report")
    op.drop_index("ix_lead_report_hub_org_created", table_name="lead_report")
    op.drop_table("lead_report")
