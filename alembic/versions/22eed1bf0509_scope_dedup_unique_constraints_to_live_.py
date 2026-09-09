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
    """Restore the plain (non-partial) UNIQUE constraints."""
    op.drop_index("uq_reviewer_name", table_name="reviewers")
    op.drop_index("ix_reviewers_name", table_name="reviewers")
    op.create_index("ix_reviewers_name", "reviewers", ["name"], unique=True)
    op.drop_index("uq_fragrance_name_brand", table_name="fragrances")
    op.create_unique_constraint(
        "uq_fragrance_name_brand", "fragrances", ["name", "brand"]
    )
