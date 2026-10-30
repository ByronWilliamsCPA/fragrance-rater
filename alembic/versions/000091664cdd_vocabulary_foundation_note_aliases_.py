"""Vocabulary foundation: note aliases, accord types, intensity source, note rank.

Revision ID: 000091664cdd
Revises: c5a9e2d7f1b4
Create Date: 2026-10-30

R6 (ML structure review X-01, X-02, X-03, X-04, X-12; ML decisions Q2, Q5). Before
pilot data exists, give the catalog one spelling per note and per accord, and stop
representing a list position as a measurement.

Schema:

- ``notes.name_key``: normalized identity key (lowercase, accents and separators
  removed), unique. ``Oak Moss`` and ``oakmoss`` become one row.
- ``note_aliases``: spellings that resolve to a canonical note under a mapping
  version. ``raw_label`` is kept verbatim and unique per version; a key has at most
  one curated decision per version.
- ``notes.category`` becomes nullable and loses the pyramid positions the Kaggle
  importer wrote into it.
- ``fragrance_notes.rank`` and a CHECK on ``position`` (X-12).
- ``accord_types``: lookup of normalized accord codes. ``fragrance_accords.accord_type``
  becomes a foreign key to it. ``intensity_source`` and ``rank`` say whether the
  weight was measured or derived from list position.

Data:

- Notes whose keys collide are merged into the note with the most fragrance links
  (ties: lowest id). Their fragrance links move to it, and each absorbed spelling
  becomes an ``observed`` alias. This changes note ids: a frozen manifest or
  prediction that recorded an absorbed id no longer joins to a note. The migration
  is meant to run before pilot data exists (ML decisions Q2); ``ml/feature_space.py``
  moves to ``fs-v2`` so later artifacts say which vocabulary they used.
- Accord codes are lowercased and whitespace-collapsed. Two spellings on one
  fragrance collapse to one row (higher intensity kept).
- ``intensity_source``: a legacy Kaggle row whose intensity sits on the importer's
  positional ladder (1.0, 0.85, 0.7, 0.55, 0.4, 0.25, 0.1) is flagged
  ``positional``; every other legacy row is ``measured``. A genuinely measured 85%
  from Kaggle is flagged positional too: the error excludes a real value from
  measured features rather than admitting a fabricated one. Its ``rank`` is the
  ladder index (not set for 0.1, which means "sixth or later").

Constraint names are the literal names the metadata naming convention gives the
models (R2, D-03). Nothing here imports application code, so the migration keeps its
meaning when the models change.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "000091664cdd"
down_revision: str | Sequence[str] | None = "c5a9e2d7f1b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MAPPING_VERSION = "nm-v1"
NOTE_POSITIONS = ("top", "heart", "base", "flat")
_POSITIONAL_LADDER = {1.0: 0, 0.85: 1, 0.7: 2, 0.55: 3, 0.4: 4, 0.25: 5, 0.1: None}

_POSITION_CHECK = "position IN ('top', 'heart', 'base', 'flat')"
_INTENSITY_SOURCE_CHECK = "intensity_source IN ('measured', 'positional', 'absent')"
_RANK_CHECK = "rank IS NULL OR rank >= 0"


def _note_key(raw: str) -> str:
    """Frozen copy of ``utils.labels.normalize_note_key`` at the time of writing."""
    import re  # noqa: PLC0415
    import unicodedata  # noqa: PLC0415

    decomposed = unicodedata.normalize("NFKD", raw)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    key = re.sub(r"[^0-9a-z]+", "", stripped.casefold())[:100]
    # A label with no letters or digits would collide with every other such
    # label; keep it distinct by falling back to the label itself.
    return key or raw[:100]


def _accord_code(raw: str) -> str:
    """Frozen copy of ``utils.labels.normalize_accord_code``."""
    import re  # noqa: PLC0415
    import unicodedata  # noqa: PLC0415

    decomposed = unicodedata.normalize("NFKD", raw)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped.casefold()).strip()


def _merge_colliding_notes(bind: sa.engine.Connection) -> dict[str, str]:
    """Merge notes that share a key; return every note's key by id."""
    notes = bind.execute(sa.text("SELECT id, name FROM notes ORDER BY id")).all()
    usage = dict(
        bind.execute(
            sa.text("SELECT note_id, COUNT(*) FROM fragrance_notes GROUP BY note_id")
        ).all()
    )
    by_key: dict[str, list[tuple[str, str]]] = {}
    for note_id, name in notes:
        by_key.setdefault(_note_key(name), []).append((note_id, name))

    keys: dict[str, str] = {}
    for key, members in by_key.items():
        members.sort(key=lambda member: (-usage.get(member[0], 0), member[0]))
        canonical_id = members[0][0]
        keys[canonical_id] = key
        for loser_id, loser_name in members[1:]:
            # A fragrance that already links the canonical note in the same
            # position keeps that link; only the duplicate is dropped.
            bind.execute(
                sa.text(
                    "DELETE FROM fragrance_notes WHERE note_id = :loser AND EXISTS ("
                    "SELECT 1 FROM fragrance_notes kept "
                    "WHERE kept.note_id = :canonical "
                    "AND kept.fragrance_id = fragrance_notes.fragrance_id "
                    "AND kept.position = fragrance_notes.position)"
                ),
                {"loser": loser_id, "canonical": canonical_id},
            )
            bind.execute(
                sa.text(
                    "UPDATE fragrance_notes SET note_id = :canonical "
                    "WHERE note_id = :loser"
                ),
                {"loser": loser_id, "canonical": canonical_id},
            )
            bind.execute(
                sa.text(
                    "INSERT INTO note_aliases "
                    "(id, raw_label, alias_key, canonical_note_id, mapping_version, "
                    "origin) VALUES (:id, :raw, :key, :canonical, :version, 'observed')"
                ),
                {
                    "id": _uuid(),
                    "raw": loser_name,
                    "key": key,
                    "canonical": canonical_id,
                    "version": MAPPING_VERSION,
                },
            )
            bind.execute(sa.text("DELETE FROM notes WHERE id = :id"), {"id": loser_id})
    return keys


def _uuid() -> str:
    import uuid  # noqa: PLC0415

    return str(uuid.uuid4())


def _normalize_accords(bind: sa.engine.Connection) -> None:
    """Fill ``accord_types`` and rewrite ``fragrance_accords`` to normalized codes."""
    rows = bind.execute(
        sa.text(
            "SELECT a.fragrance_id, a.accord_type, a.intensity, f.data_source "
            "FROM fragrance_accords a JOIN fragrances f ON f.id = a.fragrance_id "
            "ORDER BY a.fragrance_id, a.accord_type"
        )
    ).all()

    labels: dict[str, str] = {}
    taken: set[tuple[str, str]] = {(r[0], r[1]) for r in rows}
    for fragrance_id, accord_type, intensity, data_source in rows:
        code = _accord_code(accord_type)
        labels.setdefault(code, accord_type[:50])
        ladder_rank = (
            _POSITIONAL_LADDER.get(round(float(intensity), 2))
            if data_source == "kaggle"
            else None
        )
        positional = data_source == "kaggle" and round(float(intensity), 2) in (
            _POSITIONAL_LADDER
        )
        params = {
            "fragrance_id": fragrance_id,
            "old": accord_type,
            "code": code,
            "source": "positional" if positional else "measured",
            "rank": ladder_rank,
        }
        if code != accord_type and (fragrance_id, code) in taken:
            # Two spellings on one fragrance: keep one row, the larger weight.
            bind.execute(
                sa.text(
                    "UPDATE fragrance_accords SET intensity = :intensity "
                    "WHERE fragrance_id = :fragrance_id AND accord_type = :code "
                    "AND intensity < :intensity"
                ),
                {**params, "intensity": intensity},
            )
            bind.execute(
                sa.text(
                    "DELETE FROM fragrance_accords "
                    "WHERE fragrance_id = :fragrance_id AND accord_type = :old"
                ),
                params,
            )
            continue
        if code != accord_type:
            taken.discard((fragrance_id, accord_type))
            taken.add((fragrance_id, code))
        bind.execute(
            sa.text(
                "UPDATE fragrance_accords SET accord_type = :code, "
                "intensity_source = :source, rank = :rank "
                "WHERE fragrance_id = :fragrance_id AND accord_type = :old"
            ),
            params,
        )

    for code, label in sorted(labels.items()):
        bind.execute(
            sa.text("INSERT INTO accord_types (code, label) VALUES (:code, :label)"),
            {"code": code, "label": label},
        )


def upgrade() -> None:
    """Add the vocabulary tables and columns, then normalize existing rows."""
    bind = op.get_bind()

    op.create_table(
        "note_aliases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("raw_label", sa.String(length=100), nullable=False),
        sa.Column("alias_key", sa.String(length=100), nullable=False),
        sa.Column("canonical_note_id", sa.String(length=36), nullable=False),
        sa.Column("mapping_version", sa.String(length=50), nullable=False),
        sa.Column(
            "origin", sa.String(length=10), server_default="curated", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "origin IN ('curated', 'observed')", name="ck_note_aliases_origin"
        ),
        sa.ForeignKeyConstraint(
            ["canonical_note_id"],
            ["notes.id"],
            name="fk_note_aliases_canonical_note_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_note_aliases"),
        sa.UniqueConstraint(
            "raw_label",
            "mapping_version",
            name="uq_note_aliases_raw_label_mapping_version",
        ),
    )
    op.create_index(
        "uq_note_aliases_curated_key",
        "note_aliases",
        ["alias_key", "mapping_version"],
        unique=True,
        postgresql_where=sa.text("origin = 'curated'"),
        sqlite_where=sa.text("origin = 'curated'"),
    )
    op.create_index(
        "ix_note_aliases_canonical_note_id", "note_aliases", ["canonical_note_id"]
    )

    # Notes: key, merge collisions, then enforce.
    with op.batch_alter_table("notes") as batch_op:
        batch_op.add_column(sa.Column("name_key", sa.String(length=100), nullable=True))
        batch_op.alter_column(
            "category", existing_type=sa.String(length=50), nullable=True
        )
    keys = _merge_colliding_notes(bind)
    for note_id, key in keys.items():
        bind.execute(
            sa.text("UPDATE notes SET name_key = :key WHERE id = :id"),
            {"key": key, "id": note_id},
        )
    bind.execute(
        sa.text(
            "UPDATE notes SET category = NULL "
            "WHERE lower(category) IN ('top', 'heart', 'middle', 'base', 'flat')"
        )
    )
    with op.batch_alter_table("notes") as batch_op:
        batch_op.alter_column(
            "name_key", existing_type=sa.String(length=100), nullable=False
        )
        batch_op.create_unique_constraint("uq_notes_name_key", ["name_key"])

    # Fragrance notes: rank and a controlled position.
    stray = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM fragrance_notes "
            "WHERE position NOT IN ('top', 'heart', 'base', 'flat')"
        )
    ).scalar_one()
    if stray:
        msg = (
            f"{stray} fragrance_notes row(s) have a position outside "
            f"{NOTE_POSITIONS}. Correct them, then re-run the upgrade; the CHECK "
            "was not added and nothing else in this revision was applied to them."
        )
        raise RuntimeError(msg)
    with op.batch_alter_table("fragrance_notes") as batch_op:
        batch_op.add_column(sa.Column("rank", sa.Integer(), nullable=True))
        batch_op.create_check_constraint("ck_fragrance_notes_position", _POSITION_CHECK)
        batch_op.create_check_constraint("ck_fragrance_notes_rank", _RANK_CHECK)

    # Accords: lookup, provenance columns, normalized codes, then the foreign key.
    op.create_table(
        "accord_types",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("code", name="pk_accord_types"),
    )
    with op.batch_alter_table("fragrance_accords") as batch_op:
        batch_op.add_column(
            sa.Column(
                "intensity_source",
                sa.String(length=10),
                server_default="measured",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("rank", sa.Integer(), nullable=True))
    _normalize_accords(bind)
    with op.batch_alter_table("fragrance_accords") as batch_op:
        batch_op.create_check_constraint(
            "ck_fragrance_accords_intensity_source", _INTENSITY_SOURCE_CHECK
        )
        batch_op.create_check_constraint("ck_fragrance_accords_rank", _RANK_CHECK)
        batch_op.create_foreign_key(
            "fk_fragrance_accords_accord_type",
            "accord_types",
            ["accord_type"],
            ["code"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    """Drop the vocabulary structures.

    Note merges and accord lowercasing are not undone: the older schema works with
    merged notes and normalized accords. Refuses when it would discard curated alias
    decisions, which exist nowhere else.
    """
    bind = op.get_bind()
    curated = bind.execute(
        sa.text("SELECT COUNT(*) FROM note_aliases WHERE origin = 'curated'")
    ).scalar_one()
    if curated:
        msg = (
            f"{curated} curated note alias row(s) would be lost. Restore a verified "
            "pre-upgrade backup (docs/deployment/p1-release-readiness.md) instead, "
            "or delete them deliberately before downgrading."
        )
        raise RuntimeError(msg)

    with op.batch_alter_table("fragrance_accords") as batch_op:
        batch_op.drop_constraint("fk_fragrance_accords_accord_type", type_="foreignkey")
        batch_op.drop_constraint("ck_fragrance_accords_rank", type_="check")
        batch_op.drop_constraint("ck_fragrance_accords_intensity_source", type_="check")
        batch_op.drop_column("rank")
        batch_op.drop_column("intensity_source")
    op.drop_table("accord_types")

    with op.batch_alter_table("fragrance_notes") as batch_op:
        batch_op.drop_constraint("ck_fragrance_notes_rank", type_="check")
        batch_op.drop_constraint("ck_fragrance_notes_position", type_="check")
        batch_op.drop_column("rank")

    # A note with no known family gets the neutral label the NOT NULL column needs.
    bind.execute(
        sa.text("UPDATE notes SET category = 'Unknown' WHERE category IS NULL")
    )
    with op.batch_alter_table("notes") as batch_op:
        batch_op.drop_constraint("uq_notes_name_key", type_="unique")
        batch_op.alter_column(
            "category", existing_type=sa.String(length=50), nullable=False
        )
        batch_op.drop_column("name_key")

    op.drop_index("ix_note_aliases_canonical_note_id", table_name="note_aliases")
    op.drop_index("uq_note_aliases_curated_key", table_name="note_aliases")
    op.drop_table("note_aliases")
