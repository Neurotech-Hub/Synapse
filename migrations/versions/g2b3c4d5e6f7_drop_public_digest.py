"""drop public_activity_digest table and public_digest_stale columns

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-05
"""

import sqlalchemy as sa
from alembic import op

revision = "g2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("public_activity_digest")
    with op.batch_alter_table("person", schema=None) as batch_op:
        batch_op.drop_column("public_digest_stale")
    with op.batch_alter_table("organization", schema=None) as batch_op:
        batch_op.drop_column("public_digest_stale")


def downgrade():
    with op.batch_alter_table("organization", schema=None) as batch_op:
        batch_op.add_column(sa.Column("public_digest_stale", sa.Boolean(), nullable=True))
    with op.batch_alter_table("person", schema=None) as batch_op:
        batch_op.add_column(sa.Column("public_digest_stale", sa.Boolean(), nullable=True))
    op.create_table(
        "public_activity_digest",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("cited_content_item_ids_json", sa.Text(), nullable=True),
        sa.Column("input_fingerprint", sa.String(128), nullable=True),
        sa.Column("prompt_version", sa.String(64), nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
