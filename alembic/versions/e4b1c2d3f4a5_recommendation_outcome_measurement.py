"""Add recommendation impression and auditable outcome measurement.

Revision ID: e4b1c2d3f4a5
Revises: c731b42e9a01
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4b1c2d3f4a5"
down_revision: str | None = "c731b42e9a01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create immutable runs, impressions, and append-only revisions."""
    op.create_table(
        "recommendation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_id", sa.String(length=36), nullable=False),
        sa.Column("algorithm_version", sa.String(length=100), nullable=False),
        sa.Column("candidate_strategy", sa.String(length=100), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("input_manifest", sa.JSON(), nullable=False),
        sa.Column("source_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_by", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["reviewer_id"], ["reviewers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recommendation_runs_reviewer_id", "recommendation_runs", ["reviewer_id"]
    )
    op.create_index(
        "ix_recommendation_runs_created_at", "recommendation_runs", ["created_at"]
    )
    op.create_table(
        "recommendation_impressions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("fragrance_id", sa.String(length=36), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score_type", sa.String(length=50), nullable=False),
        sa.Column("score_value", sa.Float(), nullable=False),
        sa.Column("explanation_version", sa.String(length=100), nullable=True),
        sa.Column("shown_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("rank > 0"),
        sa.CheckConstraint("score_value >= 0 AND score_value <= 1"),
        sa.ForeignKeyConstraint(
            ["fragrance_id"], ["fragrances.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["recommendation_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "fragrance_id"),
        sa.UniqueConstraint("run_id", "rank"),
    )
    op.create_index(
        "ix_recommendation_impressions_run_id", "recommendation_impressions", ["run_id"]
    )
    op.create_index(
        "ix_recommendation_impressions_fragrance_id",
        "recommendation_impressions",
        ["fragrance_id"],
    )
    op.create_index(
        "ix_recommendation_impressions_shown_at",
        "recommendation_impressions",
        ["shown_at"],
    )
    op.create_table(
        "recommendation_response_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("impression_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("interested", sa.Boolean(), nullable=True),
        sa.Column("sampling_state", sa.String(length=20), nullable=True),
        sa.Column("unavailable_reason", sa.Text(), nullable=True),
        sa.Column("outcome_evaluation_id", sa.String(length=36), nullable=True),
        sa.Column("outcome_observation_id", sa.String(length=36), nullable=True),
        sa.Column("would_wear", sa.Boolean(), nullable=True),
        sa.Column("would_buy", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_by", sa.String(length=255), nullable=True),
        sa.CheckConstraint("revision > 0"),
        sa.CheckConstraint(
            "sampling_state IS NULL OR sampling_state IN "
            "('PLANNED', 'ACQUIRED', 'SAMPLED', 'UNAVAILABLE')"
        ),
        sa.CheckConstraint(
            "NOT (outcome_evaluation_id IS NOT NULL AND outcome_observation_id IS NOT NULL)"
        ),
        sa.ForeignKeyConstraint(
            ["impression_id"], ["recommendation_impressions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["outcome_evaluation_id"], ["evaluations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["outcome_observation_id"],
            ["calibration_observations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("impression_id", "revision"),
    )
    op.create_index(
        "ix_recommendation_response_revisions_impression_id",
        "recommendation_response_revisions",
        ["impression_id"],
    )
    op.create_index(
        "ix_recommendation_response_revisions_created_at",
        "recommendation_response_revisions",
        ["created_at"],
    )
    op.create_table(
        "llm_invocations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_id", sa.String(length=36), nullable=False),
        sa.Column("impression_id", sa.String(length=36), nullable=True),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("latency_ms >= 0"),
        sa.CheckConstraint("estimated_cost_usd IS NULL OR estimated_cost_usd >= 0"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["reviewers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["impression_id"], ["recommendation_impressions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_llm_invocations_reviewer_id", "llm_invocations", ["reviewer_id"]
    )
    op.create_index(
        "ix_llm_invocations_impression_id", "llm_invocations", ["impression_id"]
    )
    op.create_index("ix_llm_invocations_created_at", "llm_invocations", ["created_at"])
    op.create_table(
        "pilot_operational_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_by", sa.String(length=255), nullable=False),
        sa.CheckConstraint("event_type IN ('CONNECTIVITY_FAILURE', 'MANUAL_RECOVERY')"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["reviewers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pilot_operational_events_reviewer_id",
        "pilot_operational_events",
        ["reviewer_id"],
    )
    op.create_index(
        "ix_pilot_operational_events_occurred_at",
        "pilot_operational_events",
        ["occurred_at"],
    )


def downgrade() -> None:
    """Refuse deletion of impression and response history."""
    message = "Restore a verified pre-upgrade backup; outcome history is append-only"
    raise RuntimeError(message)
