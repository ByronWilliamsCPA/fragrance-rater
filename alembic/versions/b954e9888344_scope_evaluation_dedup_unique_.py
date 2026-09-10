"""Scope evaluation dedup unique constraint to live rows only.

Revision ID: b954e9888344
Revises: 22eed1bf0509
Create Date: 2026-09-09

The soft-delete migration (`d3c65c9cf212`) and the dedup UNIQUE migration
(`88627796b194`) interact badly for `evaluations` the same way they did for
`fragrances(name, brand)` and `reviewers.name` (fixed in `22eed1bf0509`):
`uq_evaluation_reviewer_fragrance` on `evaluations(reviewer_id, fragrance_id)`
is not scoped to `deleted_at IS NULL`, so soft-deleting a mis-entered
evaluation permanently blocks ever re-entering a rating for the same
(reviewer_id, fragrance_id) pair: the index still matches the soft-deleted
row forever.

This migration replaces the plain UNIQUE constraint with a partial
(conditional) unique index scoped to `WHERE deleted_at IS NULL`, so
uniqueness is enforced among live rows only:

- `evaluations`: drops the plain `uq_evaluation_reviewer_fragrance` UNIQUE
  constraint and recreates it as a partial unique index of the same name on
  (reviewer_id, fragrance_id).

This is a Postgres partial index (`postgresql_where`); the ORM-level
`Index` definition in `models/evaluation.py` also carries a matching
`sqlite_where` so the same semantics hold under the SQLite test database,
which builds its schema from `Base.metadata` rather than running this
migration.

This migration deliberately does not touch the pre-existing, out-of-scope
plain composite index `idx_evaluations_reviewer_fragrance` (added in
`001_initial_schema.py`, not modeled in the ORM, noted as drift by
`22eed1bf0509`): it is a separate index by a different name and is
unaffected by dropping/recreating `uq_evaluation_reviewer_fragrance`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b954e9888344"
down_revision: str | Sequence[str] | None = "22eed1bf0509"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace the evaluation dedup UNIQUE constraint with a partial unique index."""
    op.drop_constraint(
        "uq_evaluation_reviewer_fragrance", "evaluations", type_="unique"
    )
    op.create_index(
        "uq_evaluation_reviewer_fragrance",
        "evaluations",
        ["reviewer_id", "fragrance_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Restore the plain (non-partial) UNIQUE constraint.

    #CRITICAL: data-integrity: reverting to a plain (non-partial) UNIQUE
    constraint is inherently incompatible with data the partial index
    intentionally allowed: a live evaluation and a soft-deleted evaluation
    sharing the same (reviewer_id, fragrance_id) pair. This mirrors the
    identical, deliberate limitation documented on `22eed1bf0509`'s
    downgrade for `fragrances`/`reviewers`; it is not a defect in this
    migration, and there is no way to recreate a plain UNIQUE constraint
    while that coexistence still exists.
    #VERIFY: the pre-check below queries for that coexistence up front and
    raises a clear, actionable `RuntimeError` naming the conflicting pair
    instead of letting Postgres fail deep in `create_unique_constraint`
    with an opaque `IntegrityError`. If it fires, an operator must resolve
    the conflict by hand (hard-delete or restore/merge the soft-deleted
    duplicate) before retrying the downgrade. Verified via a real
    Postgres 17 round-trip: upgrade -> downgrade succeeds cleanly when no
    such duplicates exist, and fails at this pre-check (not at a cryptic
    constraint-violation error) when they do.
    """
    bind = op.get_bind()

    evaluation_dupes = bind.execute(
        sa.text(
            "SELECT reviewer_id, fragrance_id, COUNT(*) AS dup_count "
            "FROM evaluations GROUP BY reviewer_id, fragrance_id "
            "HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if evaluation_dupes:
        msg = (
            f"Cannot downgrade uq_evaluation_reviewer_fragrance to a plain "
            f"UNIQUE constraint: {len(evaluation_dupes)} "
            "(reviewer_id, fragrance_id) group(s) have more than one row, "
            "meaning a live evaluation coexists with at least one "
            "soft-deleted duplicate. A plain UNIQUE constraint cannot "
            "express that coexistence. Resolve the conflicting rows (e.g. "
            "hard-delete or restore/merge the soft-deleted duplicate) "
            "before retrying this downgrade. Example conflicting pair: "
            f"reviewer_id={evaluation_dupes[0][0]!r}, "
            f"fragrance_id={evaluation_dupes[0][1]!r}."
        )
        raise RuntimeError(msg)

    op.drop_index("uq_evaluation_reviewer_fragrance", table_name="evaluations")
    op.create_unique_constraint(
        "uq_evaluation_reviewer_fragrance",
        "evaluations",
        ["reviewer_id", "fragrance_id"],
    )
