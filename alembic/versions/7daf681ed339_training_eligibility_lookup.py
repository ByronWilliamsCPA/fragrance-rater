"""Add training_eligibilities lookup and Fragrance.training_eligibility_code.

Revision ID: 7daf681ed339
Revises: da7c14f4a129

ADR-014 builds a minimal, additive slice of the `training_eligibility` lookup
table ADR-010 already proposed but never implemented. This does not add any
non-Western fragrance data and does not touch the 33+10 baseline panel; it
closes the gap where the first fragrance outside the Michael Edwards Wheel
taxonomy would otherwise have no way to opt out of affinity scoring.

Follows the stable-code/display-label/sort_order/active lookup pattern
ADR-010 proposed for it. No existing migration already implements that
exact shape: `2c341c369192` (`fragella_lookups`) creates a reference-lookup
attempt log (id/fragrance_id/status/results), not a seeded code/label
lookup table, so this migration is the first concrete instance of the
pattern, not a repeat of an established one.

Uses `op.batch_alter_table` for the `fragrances` column/index/FK addition,
matching `da7c14f4a129`'s own rationale: SQLite (used by this migration's
integration test) cannot ALTER an already-created table to add a foreign
key directly, and batch mode is a transparent passthrough to plain
`ALTER TABLE` on PostgreSQL, so production behavior is unchanged.
"""

import sqlalchemy as sa

from alembic import op

revision = "7daf681ed339"
down_revision = "da7c14f4a129"
branch_labels = None
depends_on = None

_SEED_ROWS: tuple[dict[str, str | int | bool], ...] = (
    {
        "code": "eligible",
        "display_label": "Eligible for training",
        "sort_order": 0,
        "active": True,
    },
    {
        "code": "excluded_pending_classification",
        "display_label": "Excluded: awaiting real taxonomy classification",
        "sort_order": 10,
        "active": True,
    },
    {
        "code": "excluded_manual",
        "display_label": "Excluded: manually flagged",
        "sort_order": 20,
        "active": True,
    },
)


def upgrade() -> None:
    """Add training_eligibilities and Fragrance.training_eligibility_code.

    No existing `fragrances` row is modified: the new column is nullable
    with no default and no backfill, so NULL continues to mean "eligible"
    for every one of the existing 149 rows, exactly as it does implicitly
    today. The new `training_eligibility_code` foreign key's
    `ondelete="RESTRICT"` means a `training_eligibilities` row still
    referenced by a fragrance cannot be deleted.
    """
    op.create_table(
        "training_eligibilities",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("display_label", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("code"),
    )
    op.bulk_insert(
        sa.table(
            "training_eligibilities",
            sa.column("code", sa.String),
            sa.column("display_label", sa.String),
            sa.column("sort_order", sa.Integer),
            sa.column("active", sa.Boolean),
        ),
        list(_SEED_ROWS),
    )
    with op.batch_alter_table("fragrances") as batch_op:
        batch_op.add_column(
            sa.Column("training_eligibility_code", sa.String(length=50), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_fragrances_training_eligibility_code",
            "training_eligibilities",
            ["training_eligibility_code"],
            ["code"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_fragrances_training_eligibility_code",
            ["training_eligibility_code"],
            unique=False,
        )


def downgrade() -> None:
    """Drop the FK, index, and column, then the lookup table.

    Safely reversible in the sense ADR-010's typed-observation migration is
    not: no backfill or data transformation is needed before this downgrade
    can run, because every change `upgrade()` made was additive/nullable.

    #ASSUME: data-integrity: this still drops the `training_eligibility_code`
    column outright, so any fragrance already assigned a non-NULL code
    (e.g. `excluded_manual`) loses that value for good if this downgrade
    runs after such an assignment exists; "safely reversible" describes the
    migration mechanics (no transformation needed), not a guarantee that no
    assigned data is lost.
    #VERIFY: before running this downgrade against an environment where the
    training-eligibility feature has actually been used, confirm no
    `fragrances` row has a non-NULL `training_eligibility_code`, or capture
    those codes externally first.
    """
    with op.batch_alter_table("fragrances") as batch_op:
        batch_op.drop_index("ix_fragrances_training_eligibility_code")
        batch_op.drop_constraint(
            "fk_fragrances_training_eligibility_code", type_="foreignkey"
        )
        batch_op.drop_column("training_eligibility_code")
    op.drop_table("training_eligibilities")
