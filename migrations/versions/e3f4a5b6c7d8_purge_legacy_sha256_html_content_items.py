"""Remove legacy html_page ContentItem rows keyed by raw-byte sha256 (superseded by mainsha:).

Revision ID: e3f4a5b6c7d8
Revises: d0e1f2a3b4c5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e3f4a5b6c7d8"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade():
    """Delete ``content_item`` rows for ``html_page`` sources still using ``sha256:`` external ids."""

    op.execute(
        sa.text(
            """
            DELETE FROM content_item WHERE id IN (
                SELECT ci.id FROM content_item AS ci
                INNER JOIN source AS s ON s.id = ci.source_id
                WHERE s.kind = 'html_page'
                AND ci.external_id LIKE 'sha256:%'
            )
            """
        )
    )


def downgrade() -> None:
    """Rows cannot be restored; no-op."""

    pass
