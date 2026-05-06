"""add llm run logging and funding fetch metadata

Revision ID: l1a2b3c4d5e6
Revises: k1f2a3b4c5d6
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "l1a2b3c4d5e6"
down_revision = "k1f2a3b4c5d6"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade():
    existing = _columns("funding_opportunity")
    with op.batch_alter_table("funding_opportunity", schema=None) as batch_op:
        if "source_url_final" not in existing:
            batch_op.add_column(sa.Column("source_url_final", sa.String(length=2048), nullable=True))
        if "fetch_status_code" not in existing:
            batch_op.add_column(sa.Column("fetch_status_code", sa.Integer(), nullable=True))
        if "fetch_content_type" not in existing:
            batch_op.add_column(sa.Column("fetch_content_type", sa.String(length=160), nullable=True))
        if "fetch_error" not in existing:
            batch_op.add_column(sa.Column("fetch_error", sa.Text(), nullable=True))
        if "fetched_at" not in existing:
            batch_op.add_column(sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True))
        if "source_text_chars" not in existing:
            batch_op.add_column(sa.Column("source_text_chars", sa.Integer(), nullable=True))

    op.create_table(
        "llm_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prompt_name", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("input_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("rendered_prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("validation_errors_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(datetime('now'))")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'ok', 'failed', 'validation_failed', 'skipped')",
            name="ck_llm_run_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_run_prompt_created", "llm_run", ["prompt_name", "created_at"])
    op.create_index("ix_llm_run_provider_status", "llm_run", ["provider", "status"])
    op.create_index("ix_llm_run_source", "llm_run", ["source_type", "source_id"])
    op.create_index("ix_llm_run_input_fingerprint", "llm_run", ["input_fingerprint"])


def downgrade():
    op.drop_index("ix_llm_run_input_fingerprint", table_name="llm_run")
    op.drop_index("ix_llm_run_source", table_name="llm_run")
    op.drop_index("ix_llm_run_provider_status", table_name="llm_run")
    op.drop_index("ix_llm_run_prompt_created", table_name="llm_run")
    op.drop_table("llm_run")

    existing = _columns("funding_opportunity")
    with op.batch_alter_table("funding_opportunity", schema=None) as batch_op:
        if "source_text_chars" in existing:
            batch_op.drop_column("source_text_chars")
        if "fetched_at" in existing:
            batch_op.drop_column("fetched_at")
        if "fetch_error" in existing:
            batch_op.drop_column("fetch_error")
        if "fetch_content_type" in existing:
            batch_op.drop_column("fetch_content_type")
        if "fetch_status_code" in existing:
            batch_op.drop_column("fetch_status_code")
        if "source_url_final" in existing:
            batch_op.drop_column("source_url_final")
