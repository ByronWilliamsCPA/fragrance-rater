"""Add UNIQUE constraints preventing duplicate fragrances and evaluations.

Revision ID: 88627796b194
Revises: 6ff7e38b0060
Create Date: 2026-09-09

Major finding 8: neither `fragrances(name, brand)` nor
`evaluations(reviewer_id, fragrance_id)` had a database-level UNIQUE
constraint, so nothing stopped the same fragrance being imported twice or
the same reviewer rating the same fragrance twice beyond a racy
application-level check-then-insert in the API layer.

- `fragrances`: adds `uq_fragrance_name_brand` on (name, brand), and
  replaces the existing plain `idx_fragrances_name_brand` index with
  `ix_fragrance_search` on the same two columns (naming preserved from the
  reference implementation in project memory). Note this intentionally
  does not include `concentration`, so a legitimate EDT/EDP pair sharing a
  name and brand will collide; see the RAD comment on the `Fragrance`
  model.
- `evaluations`: adds `uq_evaluation_reviewer_fragrance` on
  (reviewer_id, fragrance_id), a hard UNIQUE. This is a default, not an
  independently re-litigated product decision: the legacy scaffold this
  branch replaced allowed repeat evaluations over time, and that choice
  was never made explicitly for this app. A hard UNIQUE matches what the
  existing application-level duplicate check already assumes.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "88627796b194"
down_revision: str | Sequence[str] | None = "6ff7e38b0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the dedup UNIQUE constraints and rename the fragrance search index."""
    op.drop_index("idx_fragrances_name_brand", table_name="fragrances")
    op.create_index("ix_fragrance_search", "fragrances", ["name", "brand"])
    op.create_unique_constraint(
        "uq_fragrance_name_brand", "fragrances", ["name", "brand"]
    )
    op.create_unique_constraint(
        "uq_evaluation_reviewer_fragrance",
        "evaluations",
        ["reviewer_id", "fragrance_id"],
    )


def downgrade() -> None:
    """Remove the dedup UNIQUE constraints and restore the original index."""
    op.drop_constraint(
        "uq_evaluation_reviewer_fragrance", "evaluations", type_="unique"
    )
    op.drop_constraint("uq_fragrance_name_brand", "fragrances", type_="unique")
    op.drop_index("ix_fragrance_search", table_name="fragrances")
    op.create_index("idx_fragrances_name_brand", "fragrances", ["name", "brand"])
