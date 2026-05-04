"""ContentItem public Latest curation overlays.

Revision ID: d0e1f2a3b4c5
Revises: c8d9e0f1a2b3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "content_item",
        sa.Column("public_feed_verdict", sa.String(length=8), nullable=True),
    )
    op.add_column("content_item", sa.Column("public_feed_display_title", sa.Text(), nullable=True))
    op.add_column("content_item", sa.Column("public_feed_display_blurb", sa.Text(), nullable=True))
    op.add_column("content_item", sa.Column("public_feed_input_fingerprint", sa.String(length=128), nullable=True))
    op.add_column("content_item", sa.Column("public_feed_curated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("content_item", sa.Column("public_feed_model_used", sa.String(length=128), nullable=True))
    op.create_index("ix_content_item_public_feed_verdict", "content_item", ["public_feed_verdict"])


def downgrade():
    op.drop_index("ix_content_item_public_feed_verdict", table_name="content_item")
    op.drop_column("content_item", "public_feed_model_used")
    op.drop_column("content_item", "public_feed_curated_at")
    op.drop_column("content_item", "public_feed_input_fingerprint")
    op.drop_column("content_item", "public_feed_display_blurb")
    op.drop_column("content_item", "public_feed_display_title")
    op.drop_column("content_item", "public_feed_verdict")
