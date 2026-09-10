"""Scope dedup unique constraints to live rows only.

Revision ID: 22eed1bf0509
Revises: d3c65c9cf212
Create Date: 2026-09-09

The soft-delete migration (`d3c65c9cf212`) and the dedup UNIQUE migration
(`88627796b194`) interact badly: `uq_fragrance_name_brand` on
`fragrances(name, brand)` and the unique index on `reviewers.name` are not
scoped to `deleted_at IS NULL`, so soft-deleting a fragrance or reviewer
permanently blocks ever recreating/re-scraping/re-seeding one with the same
natural key: the index still matches the soft-deleted row forever. For a
family app where a mis-entered fragrance or reviewer profile gets deleted
and re-added, this is a real workflow-breaker (a 409/IntegrityError forever).

This migration replaces both with partial (conditional) unique indexes
scoped to `WHERE deleted_at IS NULL`, so uniqueness is enforced among live
rows only:

- `fragrances`: drops the plain `uq_fragrance_name_brand` UNIQUE constraint
  and recreates it as a partial unique index of the same name on
  (name, brand).
- `reviewers`: drops the plain unique index `ix_reviewers_name` (created by
  the original `unique=True, index=True` column flags), recreates it as a
  non-unique index of the same name (the model now sets `index=True`
  without `unique=True`), and adds a new partial unique index
  `uq_reviewer_name` on (name,).

Both are Postgres partial indexes (`postgresql_where`); the ORM-level
`Index` definitions in `models/fragrance.py` and `models/reviewer.py` also
carry a matching `sqlite_where` so the same semantics hold under the SQLite
test database, which builds its schema from `Base.metadata` rather than
running this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "22eed1bf0509"
down_revision: str | Sequence[str] | None = "d3c65c9cf212"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace the two dedup UNIQUE constraints with partial unique indexes."""
    op.drop_constraint("uq_fragrance_name_brand", "fragrances", type_="unique")
    op.create_index(
        "uq_fragrance_name_brand",
        "fragrances",
        ["name", "brand"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index("ix_reviewers_name", table_name="reviewers")
    op.create_index("ix_reviewers_name", "reviewers", ["name"])
    op.create_index(
        "uq_reviewer_name",
        "reviewers",
        ["name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Restore the plain (non-partial) UNIQUE constraints.

    #CRITICAL: data-integrity: reverting to a plain (non-partial) UNIQUE
    constraint is inherently incompatible with data the partial index
    intentionally allowed: a live row and a soft-deleted row sharing the
    same (name, brand) / name. This is a deliberate, known limitation of
    downgrading a soft-delete-aware uniqueness fix, not a defect in this
    migration; there is no way to recreate a plain UNIQUE constraint while
    such a pair of rows still exists, because that is exactly the
    coexistence the partial index above was built to permit.
    #VERIFY: the pre-checks below query for that coexistence up front and
    raise a clear, actionable `RuntimeError` naming the conflicting rows
    instead of letting Postgres fail deep in `create_unique_constraint`
    with an opaque `IntegrityError`. If one fires, an operator must
    resolve the conflict by hand (hard-delete or rename the soft-deleted
    duplicate, or restore/merge it) before retrying the downgrade; this
    migration will not choose that resolution automatically. Verified via
    a real Postgres 17 round-trip: upgrade -> downgrade succeeds cleanly
    when no such duplicates exist, and fails at this pre-check (not at a
    cryptic constraint-violation error) when they do.
    """
    bind = op.get_bind()

    fragrance_dupes = bind.execute(
        sa.text(
            "SELECT name, brand, COUNT(*) AS dup_count FROM fragrances "
            "GROUP BY name, brand HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if fragrance_dupes:
        msg = (
            f"Cannot downgrade uq_fragrance_name_brand to a plain UNIQUE "
            f"constraint: {len(fragrance_dupes)} (name, brand) group(s) have "
            "more than one row, meaning a live row coexists with at least "
            "one soft-deleted duplicate. A plain UNIQUE constraint cannot "
            "express that coexistence. Resolve the conflicting rows (e.g. "
            "hard-delete or rename the soft-deleted duplicate) before "
            f"retrying this downgrade. Example conflicting group: "
            f"name={fragrance_dupes[0][0]!r}, brand={fragrance_dupes[0][1]!r}."
        )
        raise RuntimeError(msg)

    reviewer_dupes = bind.execute(
        sa.text(
            "SELECT name, COUNT(*) AS dup_count FROM reviewers "
            "GROUP BY name HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if reviewer_dupes:
        msg = (
            f"Cannot downgrade uq_reviewer_name to a plain UNIQUE index: "
            f"{len(reviewer_dupes)} reviewer name(s) have more than one "
            "row, meaning a live row coexists with at least one "
            "soft-deleted duplicate. Resolve the conflicting rows before "
            "retrying this downgrade. Example conflicting name: "
            f"{reviewer_dupes[0][0]!r}."
        )
        raise RuntimeError(msg)

    op.drop_index("uq_reviewer_name", table_name="reviewers")
    op.drop_index("ix_reviewers_name", table_name="reviewers")
    op.create_index("ix_reviewers_name", "reviewers", ["name"], unique=True)
    op.drop_index("uq_fragrance_name_brand", table_name="fragrances")
    op.create_unique_constraint(
        "uq_fragrance_name_brand", "fragrances", ["name", "brand"]
    )
