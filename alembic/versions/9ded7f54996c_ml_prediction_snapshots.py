"""Type controlled-observation fields.

Revision ID: 9ded7f54996c
Revises: f5c2d3e4a5b6
Create Date: 2026-09-12

Supports refining recommendation/liking projections with real ML testing:
`calibration_observations.responses` flattened validated fields
(`would_wear`, `would_buy`, opening/drydown liking, sensory dimensions,
`perceived_notes`, free-text `likes`/`dislikes`/`reminds_me_of`/`comments`)
into one untyped JSON column. That buried ML-relevant features/labels where
they could not be indexed, constrained, or queried, and the frozen training
manifest in `preference_history.py` could only forward the blob onward
unparsed. This migration adds one typed, individually bounded column per
field, backfills every existing row from its `responses` value, and retires
that column. Per the current-state ledger, live PostgreSQL calibration data
is fresh-schema verified only (no deployed pilot history exists yet to
lose); the backfill step still runs so any populated dev/staging rows
survive. Any legacy value that would violate a new column's range (the old
JSON column was never database-constrained, only validated by the API
boundary at write time) is quarantined as NULL with a logged warning naming
the row and field, rather than silently dropped or aborting the whole
migration.

The new, wholly unrelated `prediction_snapshots` table (an immutable,
model-agnostic record of a predicted rating, see ADR-009) is created by the
following revision, 72fe56efd128, which depends on this one because its
outcome-observation foreign key targets `calibration_observations.id`.

# #EDGE: data-integrity: this revision id was originally `a1b2c3d4e5f6`,
# a value that collided with another migration (fragella_lookups,
# unrelated PR, same literal id, see 2c341c369192_fragella_lookups.py)
# also merged to main - neither branch could see the other's new file at
# review time. Renamed here to a genuinely random id; no deployed
# environment had migrated to the original id (see the current-state
# ledger reference above), so this rename carries no upgrade-path risk.
"""

import logging
import math
from collections import Counter
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9ded7f54996c"
down_revision: str | None = "f5c2d3e4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger(__name__)

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


# Per-field validation rule: ("range", low, high | None) or "text" or "notes".
# `high=None` means "no upper bound", just `value >= low`.
_RULES: dict[str, tuple[object, ...]] = {
    **dict.fromkeys((*_SCORED_0_5, "projection"), ("range", 0, 5)),
    **dict.fromkeys(_SCORED_0_10, ("range", 0, 10)),
    "longevity_minutes": ("range", 0, None),
    **dict.fromkeys(_TEXT_COLUMNS, ("text",)),
    **dict.fromkeys(_JSON_COLUMNS, ("notes",)),
}


def _quarantine(name: str, value: object) -> tuple[object | None, str | None]:
    """Validate one legacy `responses[name]` value against its new column's rules.

    The old JSON column was never constrained at the database level (only by
    the API-boundary Pydantic schema, which may since have changed bounds).
    Returns `(value_to_write, warning)`: a value outside the new column's
    rules is quarantined as NULL (never fabricated or clamped) with a
    warning identifying the discarded value, rather than either silently
    dropping it with no record or letting an out-of-range legacy value abort
    the whole migration when the CHECK constraint is added afterward.

    # #CRITICAL: data-integrity: this dispatches on `_RULES[name]`, which
    # assumes every entry in `_PROMOTED_COLUMNS` has a matching `_RULES`
    # key; a mismatch raises `KeyError` and aborts the migration outright
    # instead of quarantining just the offending field.
    # #VERIFY: `_RULES` is built from `_SCORED_0_5`, `_SCORED_0_10`,
    # `_TEXT_COLUMNS`, and `_JSON_COLUMNS` by construction, so this holds as
    # long as no column is added to `_PROMOTED_COLUMNS` without a
    # corresponding rule; keep the two declarations adjacent.
    """
    if value is None:
        return None, None
    kind, *args = _RULES[name]
    if kind == "range":
        low, high = args
        return _quarantine_range(name, value, low, high)
    if kind == "text":
        return (
            (value, None)
            if isinstance(value, str)
            else (None, f"{name}={value!r} is not text")
        )
    return _quarantine_notes(name, value)


def _quarantine_range(
    name: str, value: object, low: int, high: int | None
) -> tuple[object | None, str | None]:
    """Quarantine a scalar outside `[low, high]` (or `>= low` when `high` is None).

    # #CRITICAL: data-integrity: the legacy `responses` JSON column was
    # never constrained at the database level, so a stored numeric value
    # may be a non-finite float (`inf`, `-inf`, `nan`) or an in-range float
    # that is not exactly integral (e.g. `4.7`). Passing either straight to
    # `int()` is unsafe: `int(float("inf"))` raises an unhandled
    # `OverflowError` that would crash the migration, and `int(4.7) == 4`
    # would silently fabricate/truncate a value this migration's own
    # docstring promises never to fabricate or clamp.
    # #VERIFY: both cases are checked and routed through the same
    # quarantine-as-NULL path below, before any value ever reaches `int()`.
    """
    numeric = isinstance(value, int | float) and not isinstance(value, bool)
    if numeric and isinstance(value, float) and not math.isfinite(value):
        return None, f"{name}={value!r} is not a finite number"
    in_range = numeric and low <= value and (high is None or value <= high)  # pyright: ignore[reportOperatorIssue]
    if in_range and isinstance(value, float) and value != int(value):
        return (
            None,
            f"{name}={value!r} is not an integer (legacy float would truncate)",
        )
    if in_range:
        return int(value), None  # pyright: ignore[reportArgumentType]
    bound = f"{low}-{high}" if high is not None else f">= {low}"
    return None, f"{name}={value!r} outside {bound}"


def _quarantine_notes(name: str, value: object) -> tuple[object | None, str | None]:
    """Quarantine a `perceived_notes`-shaped value: a list of strings, or None.

    # #EDGE: data-integrity: a legacy value could be a list containing
    # non-string items (numbers, nested objects) from an older, looser API
    # contract; such a list is quarantined wholesale rather than partially
    # salvaged.
    # #VERIFY: if partial salvage is ever wanted, filter `value` to its
    # string items instead of discarding the whole list.
    """
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value, None
    return None, f"{name}={value!r} is not a list of strings"


def _add_typed_columns() -> None:
    """Add the new, still-unconstrained, nullable typed columns."""
    for name in _INTEGER_COLUMNS:
        op.add_column(
            "calibration_observations", sa.Column(name, sa.Integer(), nullable=True)
        )
    for name in _TEXT_COLUMNS:
        op.add_column(
            "calibration_observations", sa.Column(name, sa.Text(), nullable=True)
        )
    for name in _JSON_COLUMNS:
        # #CRITICAL: data-integrity: `none_as_null=True` makes a Python
        # `None` write as SQL NULL instead of the JSON literal `"null"`.
        # Without it, a quarantined (never-set) value would fail the
        # `perceived_notes IS NULL OR ...` CHECK constraint added below in
        # `_add_range_constraints`, since the column would hold the text
        # "null" rather than actual SQL NULL. Keep in sync with the
        # matching `sa.column(name, sa.JSON(none_as_null=True))` in
        # `_backfill_and_drop_responses` and the ORM column definition in
        # `src/fragrance_rater/models/calibration.py`.
        # #VERIFY: any future JSON column added to `_JSON_COLUMNS` needs
        # the same flag for the same reason.
        op.add_column(
            "calibration_observations",
            sa.Column(name, sa.JSON(none_as_null=True), nullable=True),
        )


def _backfill_and_drop_responses() -> Counter[str]:
    """Backfill typed columns from `responses`, quarantining bad legacy values, then drop it.

    Runs before the range constraints are created below, so a quarantined
    legacy value (left NULL, with a logged warning) never aborts the
    migration outright; the constraints then apply only to data already
    known to satisfy them.

    Returns a per-column count of quarantined values so `upgrade()` can log
    one summary line; see `_quarantined_values`.

    # #CRITICAL: concurrency: this reads every row with a single `SELECT`
    # into memory, then issues per-row `UPDATE`s, without taking any lock
    # on `calibration_observations`. A row inserted or updated by a
    # concurrent writer after the `SELECT` but before `op.drop_column`
    # below would never be visited by this backfill loop, and its
    # `responses` data would be silently lost when the column is dropped.
    # #VERIFY: run this migration only with application writers stopped
    # (a maintenance window), which the deployment runbook already
    # requires for schema migrations; do not rely on this function alone
    # for correctness under concurrent writes.
    """
    connection = op.get_bind()
    observations = sa.table(
        "calibration_observations",
        sa.column("id", sa.String()),
        sa.column("responses", sa.JSON()),
        *(sa.column(name, sa.Integer()) for name in _INTEGER_COLUMNS),
        *(sa.column(name, sa.Text()) for name in _TEXT_COLUMNS),
        # `none_as_null=True`: see the matching note in `_add_typed_columns`.
        # Without it, `.update().values(**values)` below would write a
        # quarantined `None` as the JSON literal `"null"`, not SQL NULL.
        *(sa.column(name, sa.JSON(none_as_null=True)) for name in _JSON_COLUMNS),
    )
    rows = connection.execute(
        sa.select(observations.c.id, observations.c.responses)
    ).fetchall()
    quarantine_counts: Counter[str] = Counter()
    for row in rows:
        values, quarantined = _quarantined_values(row.id, row.responses)
        quarantine_counts.update(quarantined)
        if values:
            connection.execute(
                observations.update()
                .where(observations.c.id == row.id)
                .values(**values)
            )
    op.drop_column("calibration_observations", "responses")
    return quarantine_counts


def _quarantined_values(
    row_id: str, responses: object
) -> tuple[dict[str, object], list[str]]:
    """Return `(values_safe_to_write, quarantined_column_names)` for one row.

    Every quarantined value is logged individually (via the standard
    `logging` module, not `print`, so it survives a CI pipeline that
    discards stdout) and its column name is returned so the caller can
    aggregate a total count across all rows for one end-of-migration
    summary line.

    # #CRITICAL: data-integrity: assumes `responses` deserializes to plain
    # JSON-native Python types (`dict`, `list`, `str`, `int`, `float`,
    # `bool`, `None`); a driver that instead surfaces e.g. `decimal.Decimal`
    # for numeric JSON values would fail the `isinstance(value, int | float)`
    # checks in `_quarantine_range` and be quarantined as out-of-range
    # rather than converted, which is safe (no data is fabricated) but
    # worth knowing about if the quarantine counts look unexpectedly high.
    # #VERIFY: confirm the target database's JSON deserialization (here,
    # SQLAlchemy's `sa.JSON()` type) returns native types before relying on
    # quarantine counts as a signal of genuinely bad legacy data.
    """
    if not isinstance(responses, dict):
        logger.warning(
            "calibration_observations.id=%s has a non-object responses value "
            "(%r); leaving all promoted columns NULL",
            row_id,
            responses,
        )
        return {}, list(_PROMOTED_COLUMNS)
    values: dict[str, object] = {}
    quarantined: list[str] = []
    for name in _PROMOTED_COLUMNS:
        if name not in responses:
            continue
        validated, warning = _quarantine(name, responses[name])
        if warning:
            logger.warning(
                "calibration_observations.id=%s quarantined %s; leaving %s NULL",
                row_id,
                warning,
                name,
            )
            quarantined.append(name)
        if validated is not None:
            values[name] = validated
    return values, quarantined


def _add_range_constraints() -> None:
    """Add the CHECK constraints the typed columns above are meant to enforce.

    Uses `op.batch_alter_table` rather than bare `op.create_check_constraint`:
    SQLite (used by this migration's own integration test, see
    tests/integration/test_ml_prediction_snapshots_migration.py) cannot ALTER
    an already-created table to add a CHECK constraint directly. Batch mode
    recreates the table under the hood on SQLite to work around that, and is
    a transparent passthrough to plain `ALTER TABLE ... ADD CONSTRAINT` on
    PostgreSQL, so production behavior is unchanged.
    """
    with op.batch_alter_table("calibration_observations") as batch_op:
        for name in _SCORED_0_5:
            batch_op.create_check_constraint(
                f"ck_calibration_observations_{name}_range",
                f"{name} IS NULL OR ({name} >= 0 AND {name} <= 5)",
            )
        for name in _SCORED_0_10:
            batch_op.create_check_constraint(
                f"ck_calibration_observations_{name}_range",
                f"{name} IS NULL OR ({name} >= 0 AND {name} <= 10)",
            )
        batch_op.create_check_constraint(
            "ck_calibration_observations_projection_range",
            "projection IS NULL OR (projection >= 0 AND projection <= 5)",
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_longevity_minutes_nonnegative",
            "longevity_minutes IS NULL OR longevity_minutes >= 0",
        )
        # `perceived_notes` is plain `JSON`, not `JSONB` (see
        # `_add_typed_columns` above), so `jsonb_typeof` does not apply;
        # `json_typeof` (PostgreSQL) and `json_type` (SQLite) also aren't
        # the same function name across the two engines this repo runs
        # against (PostgreSQL in production per ADR-001, SQLite in this
        # migration's own test and the rest of the unit suite). Casting to
        # text and checking the (whitespace-trimmed) leading character is
        # portable to both and is exact for any valid JSON array.
        batch_op.create_check_constraint(
            "ck_calibration_observations_perceived_notes_is_array",
            "perceived_notes IS NULL OR ltrim(CAST(perceived_notes AS TEXT)) LIKE '[%'",
        )


def upgrade() -> None:
    """Promote responses JSON fields to typed columns."""
    _add_typed_columns()
    quarantine_counts = _backfill_and_drop_responses()
    _add_range_constraints()
    if quarantine_counts:
        logger.warning(
            "Quarantined %d values across %d columns during backfill; see "
            "prior warnings for detail",
            sum(quarantine_counts.values()),
            len(quarantine_counts),
        )


def downgrade() -> None:
    """Refuse a lossy rollback; the `responses` blob is retired, not preserved."""
    message = (
        "Restore a verified pre-upgrade backup to downgrade; this migration "
        "retires the calibration_observations.responses blob after backfilling "
        "its typed replacements, so there is no lossless in-place reversal"
    )
    raise RuntimeError(message)
