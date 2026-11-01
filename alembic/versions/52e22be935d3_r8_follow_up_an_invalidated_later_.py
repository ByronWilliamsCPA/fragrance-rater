"""R8 follow-up: an invalidated later answer does not supersede in v_training_rows.

Revision ID: 52e22be935d3
Revises: 50c1f75abb15
Create Date: 2026-11-01 09:00:00.000000

``v_training_rows`` trains only the latest pre-reveal answer per sample and
stage: an earlier answer is hidden once a later one exists. The check looked
at *any* later pre-reveal row, including one a manager had set to
``invalidated`` (raised in error, e.g. a recorder's accidental duplicate). So
voiding the mistaken later row did not bring the earlier, good answer back:
the sample dropped out of training for good, and evaluators get one blind pass
each, so there is nothing to re-collect.

The later row is now ignored for supersession when its code is
``invalidated``. A later ``questionable``, ``withheld`` or ``unreviewed`` row
still supersedes, so nothing older trains while a newer answer is under review
or has been held out. Owner decision 2026-11-01 (R8 choice A, option 2).

Only the controlled block of the view changes; no column is added or removed,
so ``v_manager_linkage`` (which does not read the view) is untouched. The view
is dropped and recreated because SQLite has no ``CREATE OR REPLACE VIEW``. The
downgrade restores 4edb5c967539's definition, verbatim.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "52e22be935d3"
down_revision: str | Sequence[str] | None = "50c1f75abb15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 4edb5c967539's definition, verbatim, for the downgrade.
V_TRAINING_ROWS_PREVIOUS_SQL = """
CREATE VIEW v_training_rows AS
SELECT
    e.id AS row_id,
    CAST('ORDINARY' AS VARCHAR(20)) AS workflow,
    e.reviewer_id AS reviewer_id,
    e.fragrance_id AS fragrance_id,
    CAST(NULL AS VARCHAR(20)) AS stage,
    CAST('1-5' AS VARCHAR(10)) AS scale,
    e.rating AS rating,
    e.evaluated_at AS observed_at,
    CAST(1 AS BOOLEAN) AS revealed
FROM evaluations AS e
JOIN fragrances AS f ON f.id = e.fragrance_id
WHERE e.training_eligibility = 'eligible'
  AND e.deleted_at IS NULL
  AND e.worn_by_reviewer_id IS NULL
  AND f.deleted_at IS NULL
  AND (
      f.training_eligibility_code IS NULL
      OR f.training_eligibility_code NOT IN
         ('excluded_pending_classification', 'excluded_manual')
  )
  AND NOT EXISTS (
      SELECT 1
      FROM calibration_memberships AS hm
      JOIN calibration_enrollments AS he ON he.program_id = hm.program_id
      WHERE he.reviewer_id = e.reviewer_id
        AND hm.fragrance_id = e.fragrance_id
        AND hm.role = 'HOLDOUT'
  )
UNION ALL
SELECT
    o.id AS row_id,
    CAST('CONTROLLED' AS VARCHAR(20)) AS workflow,
    en.reviewer_id AS reviewer_id,
    m.fragrance_id AS fragrance_id,
    o.stage AS stage,
    CAST('0-10' AS VARCHAR(10)) AS scale,
    o.liking AS rating,
    COALESCE(o.observed_at, o.created_at) AS observed_at,
    (en.revealed_at IS NOT NULL) AS revealed
FROM calibration_observations AS o
JOIN calibration_presentations AS p ON p.id = o.presentation_id
JOIN calibration_memberships AS m ON m.id = p.membership_id
JOIN calibration_sessions AS s ON s.id = p.session_id
JOIN calibration_enrollments AS en ON en.id = s.enrollment_id
JOIN fragrances AS f ON f.id = m.fragrance_id
WHERE o.training_eligibility = 'eligible'
  AND o.phase = 'PRE_REVEAL'
  AND o.liking IS NOT NULL
  AND (o.response_status IS NULL OR o.response_status = 'completed')
  AND m.role NOT IN ('HOLDOUT', 'HIDDEN_REPEAT')
  AND (
      (o.stage = 'SKIN' AND p.skin_locked_at IS NOT NULL)
      OR (o.stage = 'BLOTTER' AND p.blotter_locked_at IS NOT NULL)
  )
  AND NOT EXISTS (
      SELECT 1
      FROM calibration_observations AS later
      WHERE later.presentation_id = o.presentation_id
        AND later.stage = o.stage
        AND later.phase = 'PRE_REVEAL'
        AND (
            later.created_at > o.created_at
            OR (later.created_at = o.created_at AND later.id > o.id)
        )
  )
  AND f.deleted_at IS NULL
  AND (
      f.training_eligibility_code IS NULL
      OR f.training_eligibility_code NOT IN
         ('excluded_pending_classification', 'excluded_manual')
  )
  AND NOT EXISTS (
      SELECT 1
      FROM calibration_memberships AS hm
      JOIN calibration_enrollments AS he ON he.program_id = hm.program_id
      WHERE he.reviewer_id = en.reviewer_id
        AND hm.fragrance_id = m.fragrance_id
        AND hm.role = 'HOLDOUT'
  )
"""

_SUPERSESSION_ANCHOR = """        AND later.phase = 'PRE_REVEAL'
"""
_SUPERSESSION_EXEMPTION = """        AND later.phase = 'PRE_REVEAL'
        AND later.training_eligibility <> 'invalidated'
"""

# The new definition is the previous one plus the one exemption above. Building
# it this way (and asserting the anchor occurs exactly once) keeps the two from
# drifting apart: any other difference would have to be written out here.
assert V_TRAINING_ROWS_PREVIOUS_SQL.count(_SUPERSESSION_ANCHOR) == 1
V_TRAINING_ROWS_SQL = V_TRAINING_ROWS_PREVIOUS_SQL.replace(
    _SUPERSESSION_ANCHOR, _SUPERSESSION_EXEMPTION
)


def upgrade() -> None:
    """Recreate ``v_training_rows`` with the invalidated-row exemption."""
    op.execute("DROP VIEW IF EXISTS v_training_rows")
    op.execute(V_TRAINING_ROWS_SQL)


def downgrade() -> None:
    """Restore the previous definition."""
    op.execute("DROP VIEW IF EXISTS v_training_rows")
    op.execute(V_TRAINING_ROWS_PREVIOUS_SQL)
