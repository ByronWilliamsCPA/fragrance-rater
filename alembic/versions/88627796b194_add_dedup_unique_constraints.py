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

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "88627796b194"
down_revision: str | Sequence[str] | None = "6ff7e38b0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# #CRITICAL: data-integrity: keep the oldest row per duplicate group
# (created_at ascending), tie-broken by id ascending for a fully
# deterministic order when timestamps collide. `deleted_at` does not exist
# yet at this point in migration history (it is added later by
# `d3c65c9cf212`), so there is no soft-delete column available to spare
# the non-canonical duplicates: they are hard-deleted here.
# #VERIFY: hard-deleting a duplicate `fragrances` row cascades
# (ON DELETE CASCADE) to its `fragrance_notes`, `fragrance_accords`, and
# `evaluations` rows. That is intentional for `fragrance_notes` /
# `fragrance_accords` (they only describe the being-removed duplicate
# catalog entry and are re-derivable by re-scraping/re-seeding), but it
# also deletes any evaluation recorded against that specific duplicate
# row. Before running this migration against real production data, review
# whether any duplicate group actually carries distinct evaluation
# history on its non-canonical rows; this migration cannot distinguish
# "harmless catalog duplicate" from "someone rated the wrong copy" and
# does not attempt reassignment, since inferring the correct target
# fragrance for a reassigned evaluation is a judgment call, not a safe
# default.
_DEDUP_FRAGRANCES_SQL = """
    WITH ranked AS (
        SELECT
            id,
            ROW_NUMBER() OVER (
                PARTITION BY name, brand
                ORDER BY created_at ASC, id ASC
            ) AS row_num
        FROM fragrances
    )
    DELETE FROM fragrances
    WHERE id IN (SELECT id FROM ranked WHERE row_num > 1)
"""

# Runs after `_DEDUP_FRAGRANCES_SQL` so any evaluations that were only
# duplicated because they pointed at a since-removed duplicate fragrance
# are already gone via cascade; this catches genuine duplicate
# evaluations recorded twice against the same surviving fragrance. Same
# tie-break rule: keep the oldest row (created_at ASC, id ASC).
_DEDUP_EVALUATIONS_SQL = """
    WITH ranked AS (
        SELECT
            id,
            ROW_NUMBER() OVER (
                PARTITION BY reviewer_id, fragrance_id
                ORDER BY created_at ASC, id ASC
            ) AS row_num
        FROM evaluations
    )
    DELETE FROM evaluations
    WHERE id IN (SELECT id FROM ranked WHERE row_num > 1)
"""


def upgrade() -> None:
    """Deduplicate pre-existing rows, then add the dedup UNIQUE constraints.

    This migration's own docstring already acknowledges that duplicate
    (name, brand) fragrances and duplicate (reviewer_id, fragrance_id)
    evaluations were possible before now (nothing enforced it below the
    racy application-level check). Adding the UNIQUE constraints directly
    without resolving pre-existing duplicates first would make this
    migration fail outright against any real database that has one, so
    the de-duplication runs first. See the RAD comments above the SQL
    constants for the tie-breaking rule and its trade-offs.
    """
    bind = op.get_bind()
    bind.execute(sa.text(_DEDUP_FRAGRANCES_SQL))
    bind.execute(sa.text(_DEDUP_EVALUATIONS_SQL))

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
    """Remove the dedup UNIQUE constraints and restore the original index.

    This intentionally does not, and cannot, undo the de-duplication
    performed in `upgrade()`: rows hard-deleted there are gone with no
    retained record of what was removed (no soft-delete column existed at
    this point in migration history), so there is nothing to restore. A
    migration cannot resurrect data it deleted; this is expected and is
    not a bug to fix, only a fact to document.
    """
    op.drop_constraint(
        "uq_evaluation_reviewer_fragrance", "evaluations", type_="unique"
    )
    op.drop_constraint("uq_fragrance_name_brand", "fragrances", type_="unique")
    op.drop_index("ix_fragrance_search", table_name="fragrances")
    op.create_index("idx_fragrances_name_brand", "fragrances", ["name", "brand"])
