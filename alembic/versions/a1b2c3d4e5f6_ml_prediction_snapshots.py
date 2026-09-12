"""Type controlled-observation fields and add ML prediction snapshots.

Revision ID: a1b2c3d4e5f6
Revises: f5c2d3e4a5b6
Create Date: 2026-09-12

Supports refining recommendation/liking projections with real ML testing:

- `calibration_observations.responses` flattened validated fields
  (`would_wear`, `would_buy`, opening/drydown liking, sensory dimensions,
  `perceived_notes`, free-text `likes`/`dislikes`/`reminds_me_of`/
  `comments`) into one untyped JSON column. That buried ML-relevant
  features/labels where they could not be indexed, constrained, or
  queried, and the frozen training manifest in `preference_history.py`
  could only forward the blob onward unparsed. This migration adds one
  typed, individually bounded column per field, backfills every existing
  row from its `responses` value, and retires that column. Per the
  current-state ledger, live PostgreSQL calibration data is fresh-schema
  verified only (no deployed pilot history exists yet to lose); the
  backfill step still runs so any populated dev/staging rows survive.
- Adds `prediction_snapshots`: an immutable, model-agnostic record of a
  predicted rating for one evaluator/fragrance pair, frozen before the
  real outcome is known, with a one-time append-only outcome link so
  prediction error can be measured honestly (ADR-009).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f5c2d3e4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# One (column, SQLAlchemy type) pair per `responses` key being promoted,
# reused by both the ADD COLUMN loop and the backfill loop below.
_SCORED_0_5 = (
    "confidence",
    "sweetness",
    "freshness",
    "density",
    "familiarity",
    "dryness",
    "clean_soapy",
    "earthy_rooty",
    "bodily_animalic",
    "discomfort",
)
_SCORED_0_10 = (
    "opening_liking",
    "drydown_liking",
    "would_wear",
    "would_buy",
    "artistic_appreciation",
)
_INTEGER_COLUMNS = (*_SCORED_0_5, *_SCORED_0_10, "projection", "longevity_minutes")
_TEXT_COLUMNS = ("likes", "dislikes", "reminds_me_of", "comments")
_JSON_COLUMNS = ("perceived_notes",)
_PROMOTED_COLUMNS = (*_INTEGER_COLUMNS, *_TEXT_COLUMNS, *_JSON_COLUMNS)


def upgrade() -> None:
    """Promote responses JSON fields to typed columns; add prediction snapshots."""
    for name in _INTEGER_COLUMNS:
        op.add_column(
            "calibration_observations", sa.Column(name, sa.Integer(), nullable=True)
        )
    for name in _TEXT_COLUMNS:
        op.add_column(
            "calibration_observations", sa.Column(name, sa.Text(), nullable=True)
        )
    for name in _JSON_COLUMNS:
        op.add_column(
            "calibration_observations", sa.Column(name, sa.JSON(), nullable=True)
        )
    for name in _SCORED_0_5:
        op.create_check_constraint(
            f"ck_calibration_observations_{name}_range",
            "calibration_observations",
            f"{name} IS NULL OR ({name} >= 0 AND {name} <= 5)",
        )
    for name in _SCORED_0_10:
        op.create_check_constraint(
            f"ck_calibration_observations_{name}_range",
            "calibration_observations",
            f"{name} IS NULL OR ({name} >= 0 AND {name} <= 10)",
        )
    op.create_check_constraint(
        "ck_calibration_observations_projection_range",
        "calibration_observations",
        "projection IS NULL OR (projection >= 0 AND projection <= 5)",
    )
    op.create_check_constraint(
        "ck_calibration_observations_longevity_minutes_nonnegative",
        "calibration_observations",
        "longevity_minutes IS NULL OR longevity_minutes >= 0",
    )

    # Backfill every existing row from its legacy `responses` blob before
    # dropping it. Idempotent by construction: it only ever reads from
    # `responses` and writes into the brand-new typed columns above.
    connection = op.get_bind()
    observations = sa.table(
        "calibration_observations",
        sa.column("id", sa.String()),
        sa.column("responses", sa.JSON()),
        *(sa.column(name, sa.Integer()) for name in _INTEGER_COLUMNS),
        *(sa.column(name, sa.Text()) for name in _TEXT_COLUMNS),
        *(sa.column(name, sa.JSON()) for name in _JSON_COLUMNS),
    )
    rows = connection.execute(
        sa.select(observations.c.id, observations.c.responses)
    ).fetchall()
    for row in rows:
        responses = row.responses or {}
        if not isinstance(responses, dict):
            continue
        values = {
            name: responses.get(name) for name in _PROMOTED_COLUMNS if name in responses
        }
        if not values:
            continue
        connection.execute(
            observations.update().where(observations.c.id == row.id).values(**values)
        )
    op.drop_column("calibration_observations", "responses")

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
    """Refuse a lossy rollback; the `responses` blob is retired, not preserved."""
    message = (
        "Restore a verified pre-upgrade backup to downgrade; this migration "
        "retires the calibration_observations.responses blob after backfilling "
        "its typed replacements, so there is no lossless in-place reversal"
    )
    raise RuntimeError(message)
