"""Create prediction_snapshots table.

Revision ID: 72fe56efd128
Revises: 9ded7f54996c
Create Date: 2026-09-12

Split out of 9ded7f54996c (ml_prediction_snapshots, which promotes
calibration_observations.responses to typed columns): this half is a
wholly new table, `prediction_snapshots`, an immutable, model-agnostic
record of a predicted rating for one evaluator/fragrance pair, frozen
before the real outcome is known, with a one-time append-only outcome
link so prediction error can be measured honestly (ADR-009). It depends
on `calibration_observations` already having its final, typed shape (the
outcome-observation foreign key below points at it), hence the split
into a second, dependent revision rather than one migration doing both
unrelated things.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "72fe56efd128"
down_revision: str | None = "9ded7f54996c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create `prediction_snapshots` and its indexes."""
    op.create_table(
        "prediction_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_id", sa.String(length=36), nullable=False),
        sa.Column("fragrance_id", sa.String(length=36), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=36), nullable=True),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("feature_snapshot_version", sa.String(length=100), nullable=True),
        sa.Column(
            "predicted_scale",
            sa.String(length=20),
            nullable=False,
            server_default="0-10",
        ),
        sa.Column("predicted_rating", sa.Float(), nullable=True),
        sa.Column("uncertainty", sa.Float(), nullable=True),
        sa.Column("percentile_rank", sa.Float(), nullable=True),
        sa.Column("scenario", sa.String(length=100), nullable=True),
        sa.Column("input_manifest", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_by", sa.String(length=255), nullable=True),
        sa.Column("outcome_evaluation_id", sa.String(length=36), nullable=True),
        sa.Column("outcome_observation_id", sa.String(length=36), nullable=True),
        sa.Column("outcome_linked_at", sa.DateTime(), nullable=True),
        sa.Column("outcome_recorded_by", sa.String(length=255), nullable=True),
        sa.CheckConstraint("uncertainty IS NULL OR uncertainty >= 0"),
        sa.CheckConstraint(
            "percentile_rank IS NULL OR (percentile_rank >= 0 AND percentile_rank <= 100)"
        ),
        sa.CheckConstraint(
            "NOT (outcome_evaluation_id IS NOT NULL AND outcome_observation_id IS NOT NULL)"
        ),
        # Excludes NaN (`predicted_rating = predicted_rating` is false for
        # NaN under IEEE754) and +/-Infinity (neither satisfies both bounds)
        # without a dialect-specific cast, since this same check runs on
        # both PostgreSQL (production, ADR-001) and SQLite (this repo's
        # migration/unit tests, see tests/integration/test_calibration_migration.py).
        sa.CheckConstraint(
            "predicted_rating IS NULL OR "
            "(predicted_rating = predicted_rating "
            "AND predicted_rating > -1e308 AND predicted_rating < 1e308)",
            name="ck_prediction_snapshot_predicted_rating_finite",
        ),
        # Ties `outcome_linked_at`'s nullity to both outcome-id columns':
        # the link timestamp is set if and only if an outcome has actually
        # been recorded, so a snapshot can't be "linked" with no outcome
        # attached, or carry an outcome with no linking timestamp.
        sa.CheckConstraint(
            "(outcome_linked_at IS NULL) = "
            "(outcome_evaluation_id IS NULL AND outcome_observation_id IS NULL)",
            name="ck_prediction_snapshot_outcome_linked_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["checkpoint_id"], ["calibration_checkpoints.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["fragrance_id"], ["fragrances.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["outcome_evaluation_id"], ["evaluations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["outcome_observation_id"],
            ["calibration_observations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["reviewers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_prediction_snapshots_reviewer_id"),
        "prediction_snapshots",
        ["reviewer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prediction_snapshots_fragrance_id"),
        "prediction_snapshots",
        ["fragrance_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prediction_snapshots_checkpoint_id"),
        "prediction_snapshots",
        ["checkpoint_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prediction_snapshots_created_at"),
        "prediction_snapshots",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Refuse a lossy rollback; frozen prediction history is not disposable."""
    message = (
        "Restore a verified pre-upgrade backup to downgrade; this migration "
        "creates prediction_snapshots, an append-only record of frozen "
        "predictions, so there is no lossless in-place reversal"
    )
    raise RuntimeError(message)
