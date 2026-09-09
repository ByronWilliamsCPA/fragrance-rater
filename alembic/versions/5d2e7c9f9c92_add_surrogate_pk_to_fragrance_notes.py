"""Add surrogate id PK to fragrance_notes and allow repeated-position notes.

Revision ID: 5d2e7c9f9c92
Revises: 88627796b194
Create Date: 2026-09-09

Critical finding 3: FragranceNote's composite primary key was
(fragrance_id, note_id) - it excluded `position`, so the same note
appearing in two pyramid positions for one fragrance (e.g. musk in both
heart and base) collided on the primary key and crashed the import. The
ratified fix is a real surrogate `id` primary key (matching the
UUID-string style used by every other table in this schema), not simply
widening the composite PK to include `position`, plus a
UNIQUE(fragrance_id, note_id, position) constraint so a genuine duplicate
(the same note in the same position twice) is still rejected rather than
silently accepted.

This migration:
- adds a nullable `id` column, backfills it with a random UUID per
  existing row, then makes it NOT NULL and the primary key
- drops the old (fragrance_id, note_id) composite primary key
- adds UNIQUE(fragrance_id, note_id, position)

Paired with per-row SAVEPOINT isolation added in the importer/scraper so
a single conflicting row no longer aborts the whole import session.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d2e7c9f9c92"
down_revision: str | Sequence[str] | None = "88627796b194"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the surrogate id PK and the position-aware UNIQUE constraint."""
    op.add_column("fragrance_notes", sa.Column("id", sa.String(36), nullable=True))
    # #ASSUME: data-integrity: gen_random_uuid() is built into Postgres core
    # since v13 (this project targets postgres:16, see docker-compose.yml),
    # so no extension needs to be enabled for this backfill.
    # #VERIFY: if this migration is ever run against an older Postgres,
    # enable pgcrypto first or swap in uuid_generate_v4().
    op.execute(
        "UPDATE fragrance_notes SET id = gen_random_uuid()::text WHERE id IS NULL"
    )
    op.alter_column("fragrance_notes", "id", nullable=False)
    op.drop_constraint("fragrance_notes_pkey", "fragrance_notes", type_="primary")
    op.create_primary_key("fragrance_notes_pkey", "fragrance_notes", ["id"])
    op.create_unique_constraint(
        "uq_fragrance_note_position",
        "fragrance_notes",
        ["fragrance_id", "note_id", "position"],
    )


def downgrade() -> None:
    """Restore the composite primary key and drop the surrogate id."""
    op.drop_constraint("uq_fragrance_note_position", "fragrance_notes", type_="unique")
    op.drop_constraint("fragrance_notes_pkey", "fragrance_notes", type_="primary")
    op.create_primary_key(
        "fragrance_notes_pkey", "fragrance_notes", ["fragrance_id", "note_id"]
    )
    op.drop_column("fragrance_notes", "id")
