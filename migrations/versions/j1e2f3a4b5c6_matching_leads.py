"""add matching and collaboration hypothesis tables

Revision ID: j1e2f3a4b5c6
Revises: i1d2e3f4a5b6
Create Date: 2026-05-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "j1e2f3a4b5c6"
down_revision = "i1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "match_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_type", sa.String(length=80), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("pipeline_version", sa.String(length=80), nullable=False, server_default=sa.text("'deterministic_v1'")),
        sa.Column("candidates_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("scored_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("input_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("params_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("result_summary_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(datetime('now'))")),
        sa.CheckConstraint("status IN ('queued', 'running', 'ok', 'failed')", name="ck_match_run_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_match_run_type_created", "match_run", ["run_type", "created_at"])
    op.create_index("ix_match_run_source", "match_run", ["source_type", "source_id"])
    op.create_index("ix_match_run_status", "match_run", ["status"])

    op.create_table(
        "match_edge",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("match_run_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("match_type", sa.String(length=80), nullable=False),
        sa.Column("score_total", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("score_topic_fit", sa.Float(), nullable=True),
        sa.Column("score_method_fit", sa.Float(), nullable=True),
        sa.Column("score_hub_fit", sa.Float(), nullable=True),
        sa.Column("score_funding_fit", sa.Float(), nullable=True),
        sa.Column("score_evidence_strength", sa.Float(), nullable=True),
        sa.Column("score_recency", sa.Float(), nullable=True),
        sa.Column("score_strategic_value", sa.Float(), nullable=True),
        sa.Column("score_effort_reasonableness", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("public_rationale", sa.Text(), nullable=True),
        sa.Column("private_rationale", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("features_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("synthesized_json", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("pipeline_version", sa.String(length=80), nullable=False, server_default=sa.text("'deterministic_v1'")),
        sa.Column("input_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'needs_review'")),
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default=sa.text("'private'")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(datetime('now'))")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(datetime('now'))")),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('candidate', 'scored', 'needs_review', 'reviewed', 'accepted', 'rejected', 'hidden', 'archived', 'stale')",
            name="ck_match_edge_status",
        ),
        sa.CheckConstraint(
            "visibility IN ('private', 'public_safe', 'public', 'hidden')",
            name="ck_match_edge_visibility",
        ),
        sa.ForeignKeyConstraint(["match_run_id"], ["match_run.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "source_id", "target_type", "target_id", "match_type", name="uq_match_edge_pair_type"),
    )
    op.create_index("ix_match_edge_source", "match_edge", ["source_type", "source_id"])
    op.create_index("ix_match_edge_target", "match_edge", ["target_type", "target_id"])
    op.create_index("ix_match_edge_type_status", "match_edge", ["match_type", "status"])
    op.create_index("ix_match_edge_status_score", "match_edge", ["status", "score_total"])

    op.create_table(
        "collaboration_hypothesis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("priority", sa.String(length=32), nullable=False, server_default=sa.text("'normal'")),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("idea_id", sa.Integer(), nullable=True),
        sa.Column("funding_opportunity_id", sa.Integer(), nullable=True),
        sa.Column("primary_match_edge_id", sa.Integer(), nullable=True),
        sa.Column("related_match_edge_ids_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("hypothesis_summary", sa.Text(), nullable=True),
        sa.Column("evidence_summary", sa.Text(), nullable=True),
        sa.Column("hub_fit_summary", sa.Text(), nullable=True),
        sa.Column("funding_fit_summary", sa.Text(), nullable=True),
        sa.Column("effort_summary", sa.Text(), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("outreach_angle", sa.Text(), nullable=True),
        sa.Column("public_safe_summary", sa.Text(), nullable=True),
        sa.Column("private_notes", sa.Text(), nullable=True),
        sa.Column("score_fit", sa.Float(), nullable=True),
        sa.Column("score_timing", sa.Float(), nullable=True),
        sa.Column("score_funding", sa.Float(), nullable=True),
        sa.Column("score_effort", sa.Float(), nullable=True),
        sa.Column("score_relationship", sa.Float(), nullable=True),
        sa.Column("score_strategic", sa.Float(), nullable=True),
        sa.Column("score_total", sa.Float(), nullable=True),
        sa.Column("score_breakdown_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("evidence_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("synthesized_json", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("pipeline_version", sa.String(length=80), nullable=False, server_default=sa.text("'deterministic_v1'")),
        sa.Column("input_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(datetime('now'))")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(datetime('now'))")),
        sa.CheckConstraint(
            "status IN ('draft', 'needs_review', 'reviewed', 'active', 'contacted', 'dismissed', 'archived', 'stale')",
            name="ck_collaboration_hypothesis_status",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'normal', 'high', 'strategic')",
            name="ck_collaboration_hypothesis_priority",
        ),
        sa.ForeignKeyConstraint(["funding_opportunity_id"], ["funding_opportunity.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["idea_id"], ["idea.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["primary_match_edge_id"], ["match_edge.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collab_hypothesis_status_priority", "collaboration_hypothesis", ["status", "priority"])
    op.create_index("ix_collab_hypothesis_target", "collaboration_hypothesis", ["target_type", "target_id"])
    op.create_index("ix_collab_hypothesis_idea", "collaboration_hypothesis", ["idea_id"])
    op.create_index("ix_collab_hypothesis_funding", "collaboration_hypothesis", ["funding_opportunity_id"])


def downgrade():
    op.drop_index("ix_collab_hypothesis_funding", table_name="collaboration_hypothesis")
    op.drop_index("ix_collab_hypothesis_idea", table_name="collaboration_hypothesis")
    op.drop_index("ix_collab_hypothesis_target", table_name="collaboration_hypothesis")
    op.drop_index("ix_collab_hypothesis_status_priority", table_name="collaboration_hypothesis")
    op.drop_table("collaboration_hypothesis")
    op.drop_index("ix_match_edge_status_score", table_name="match_edge")
    op.drop_index("ix_match_edge_type_status", table_name="match_edge")
    op.drop_index("ix_match_edge_target", table_name="match_edge")
    op.drop_index("ix_match_edge_source", table_name="match_edge")
    op.drop_table("match_edge")
    op.drop_index("ix_match_run_status", table_name="match_run")
    op.drop_index("ix_match_run_source", table_name="match_run")
    op.drop_index("ix_match_run_type_created", table_name="match_run")
    op.drop_table("match_run")
