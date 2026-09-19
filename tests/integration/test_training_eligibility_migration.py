"""Exercise the training_eligibility migration (7daf681ed339, ADR-014)."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models import Base


def _fk_enforcing_engine():
    """A SQLite engine with foreign-key enforcement turned on.

    SQLite ignores FK constraints by default; the standard SQLAlchemy
    recipe is a `connect` event that issues `PRAGMA foreign_keys=ON` on
    every new DBAPI connection, since the pragma is a per-connection
    setting (and a no-op if issued mid-transaction).
    """
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


_VERSIONS = Path(__file__).parents[2] / "alembic/versions"


def _load_migration(filename: str):
    path = _VERSIONS / filename
    spec = importlib.util.spec_from_file_location(filename, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_migration():
    return _load_migration("7daf681ed339_training_eligibility_lookup.py")


def load_prior_migration():
    """Load da7c14f4a129, the migration immediately prior to 7daf681ed339.

    ``down_revision`` on 7daf681ed339 points at da7c14f4a129, so this is
    the real migration whose ``upgrade()`` a deployment's Alembic history
    would have already run before 7daf681ed339 ever executes.
    """
    return _load_migration("da7c14f4a129_add_worn_by_reviewer_id_to_evaluations.py")


def _upgrade_to_pre_training_eligibility_schema(connection):
    """Build the schema exactly as it stood right before 7daf681ed339.

    ``Base.metadata`` reflects the current ORM model, which already
    declares everything both this migration and da7c14f4a129 (the migration
    immediately prior in the chain) add, so both are stripped back out
    here first. da7c14f4a129's own contribution is then restored by
    running its actual ``upgrade()`` below, the same literal-migration-chain
    pattern ``test_ml_prediction_snapshots_migration.py`` uses to reconstruct
    ``c731b42e9a01``'s state before testing on top of it, rather than
    hand-synthesizing what that prior migration would produce. This keeps
    the schema this migration's own ``upgrade()`` runs against the real
    pre-7daf681ed339 state a deployment's Alembic history would produce,
    not a hand-built approximation of it.
    """
    Base.metadata.create_all(connection)
    # The ORM's inline `ForeignKey(...)`s leave both constraints unnamed, so
    # (mirroring test_worn_by_reviewer_migration.py's own helper) the
    # indexes are dropped by plain SQL first, and dropping each column in
    # batch mode implicitly drops its unnamed FK as part of the table
    # rebuild, rather than trying to `drop_constraint` it by the name the
    # real migrations assign (which only exists once those migrations
    # themselves have run).
    connection.execute(text("DROP INDEX ix_evaluations_worn_by_reviewer_id"))
    connection.execute(text("DROP INDEX ix_fragrances_training_eligibility_code"))
    op = Operations(MigrationContext.configure(connection))
    with op.batch_alter_table("evaluations") as batch_op:
        batch_op.drop_constraint(
            "ck_evaluations_worn_by_reviewer_not_self", type_="check"
        )
        batch_op.drop_column("worn_by_reviewer_id")
    with op.batch_alter_table("fragrances") as batch_op:
        batch_op.drop_column("training_eligibility_code")
    op.drop_table("training_eligibilities")

    with Operations.context(MigrationContext.configure(connection)):
        load_prior_migration().upgrade()


def _seed_fragrance(connection) -> None:
    connection.execute(
        text(
            "INSERT INTO fragrances(id, name, brand, concentration, gender_target, "
            "primary_family, subfamily, data_source) VALUES "
            "('f1', 'Scent', 'House', 'EDP', 'Unisex', 'Woody', 'Woody', 'manual')"
        )
    )


def test_upgrade_creates_lookup_table_and_seeds_three_rows():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgrade_to_pre_training_eligibility_schema(connection)
        _seed_fragrance(connection)

        with Operations.context(MigrationContext.configure(connection)):
            load_migration().upgrade()

        rows = connection.execute(
            text(
                "SELECT code, display_label, sort_order, active "
                "FROM training_eligibilities ORDER BY sort_order"
            )
        ).all()
        assert [r.code for r in rows] == [
            "eligible",
            "excluded_pending_classification",
            "excluded_manual",
        ]
        assert [r.sort_order for r in rows] == [0, 10, 20]
        assert all(r.active for r in rows)
        assert [r.display_label for r in rows] == [
            "Eligible for training",
            "Excluded: awaiting real taxonomy classification",
            "Excluded: manually flagged",
        ]


def test_upgrade_adds_nullable_column_with_no_backfill():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgrade_to_pre_training_eligibility_schema(connection)
        _seed_fragrance(connection)

        with Operations.context(MigrationContext.configure(connection)):
            load_migration().upgrade()

        columns = {c["name"] for c in inspect(connection).get_columns("fragrances")}
        assert "training_eligibility_code" in columns

        value = connection.execute(
            text("SELECT training_eligibility_code FROM fragrances WHERE id = 'f1'")
        ).scalar_one()
        assert value is None

        indexes = {i["name"] for i in inspect(connection).get_indexes("fragrances")}
        assert "ix_fragrances_training_eligibility_code" in indexes

        fks = inspect(connection).get_foreign_keys("fragrances")
        assert any(
            fk["constrained_columns"] == ["training_eligibility_code"]
            and fk["referred_table"] == "training_eligibilities"
            for fk in fks
        )


def test_upgrade_rejects_invalid_training_eligibility_code():
    engine = _fk_enforcing_engine()
    with engine.begin() as connection:
        _upgrade_to_pre_training_eligibility_schema(connection)
        _seed_fragrance(connection)

        with Operations.context(MigrationContext.configure(connection)):
            load_migration().upgrade()

        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "UPDATE fragrances SET training_eligibility_code = 'not-a-code' "
                    "WHERE id = 'f1'"
                )
            )


def test_seed_rows_agree_with_training_ineligible_codes():
    """ADR-014: the migration's seed rows and `TRAINING_INELIGIBLE_CODES`
    (`core/vocabulary.py`) must describe the same excluded set. A code
    seeded here but absent from that frozenset (or vice versa) is exactly
    the kind of drift `core/vocabulary.py`'s own docstring already warns
    about for `gender_target` (the scraper and the API/importer
    disagreeing on case).
    """
    from fragrance_rater.core.vocabulary import TRAINING_INELIGIBLE_CODES

    migration = load_migration()
    seeded_codes = {row["code"] for row in migration._SEED_ROWS}
    excluded_seeded_codes = {
        row["code"] for row in migration._SEED_ROWS if row["code"] != "eligible"
    }

    assert excluded_seeded_codes == set(TRAINING_INELIGIBLE_CODES)
    assert TRAINING_INELIGIBLE_CODES.issubset(seeded_codes)


def test_fk_restrict_blocks_deleting_referenced_training_eligibility_row():
    """ADR-014: `ondelete="RESTRICT"` on
    `fk_fragrances_training_eligibility_code` must block deleting a
    `training_eligibilities` row still referenced by a fragrance, not
    silently null out or cascade-delete the referencing row.
    """
    engine = _fk_enforcing_engine()
    with engine.begin() as connection:
        Base.metadata.create_all(connection)
        connection.execute(
            text(
                "INSERT INTO training_eligibilities"
                "(code, display_label, sort_order, active) VALUES "
                "('excluded_manual', 'Excluded: manually flagged', 20, 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO fragrances(id, name, brand, concentration, "
                "gender_target, primary_family, subfamily, data_source, "
                "training_eligibility_code) VALUES "
                "('f3', 'Restricted Scent', 'House', 'EDP', 'Unisex', "
                "'Woody', 'Woody', 'manual', 'excluded_manual')"
            )
        )

        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "DELETE FROM training_eligibilities WHERE code = 'excluded_manual'"
                )
            )


@pytest.mark.parametrize("training_eligibility_code", [None, "excluded_manual"])
def test_downgrade_drops_column_fk_index_and_table(training_eligibility_code):
    """Downgrade drops the column, FK, index, and lookup table cleanly.

    Covers both the all-NULL case (no fragrance ever assigned a code) and
    the realistic case where a fragrance carries a real, seeded
    ``training_eligibilities.code`` at the time downgrade runs. Either way,
    downgrade must succeed without orphaning or corrupting the row's other
    data.
    """
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgrade_to_pre_training_eligibility_schema(connection)
        _seed_fragrance(connection)

        with Operations.context(MigrationContext.configure(connection)):
            load_migration().upgrade()

        if training_eligibility_code is not None:
            connection.execute(
                text(
                    "UPDATE fragrances SET training_eligibility_code = :code "
                    "WHERE id = 'f1'"
                ),
                {"code": training_eligibility_code},
            )

        with Operations.context(MigrationContext.configure(connection)):
            load_migration().downgrade()

        columns = {c["name"] for c in inspect(connection).get_columns("fragrances")}
        assert "training_eligibility_code" not in columns

        tables = inspect(connection).get_table_names()
        assert "training_eligibilities" not in tables

        # The fragrance row itself, and its other data, survive the
        # downgrade uncorrupted regardless of whether it carried a code.
        row = connection.execute(
            text("SELECT name, brand, primary_family FROM fragrances WHERE id = 'f1'")
        ).one()
        assert row.name == "Scent"
        assert row.brand == "House"
        assert row.primary_family == "Woody"

        # A plain fragrance insert (no lookup table, no eligibility column
        # to reference) still succeeds after downgrade.
        connection.execute(
            text(
                "INSERT INTO fragrances(id, name, brand, concentration, "
                "gender_target, primary_family, subfamily, data_source) VALUES "
                "('f2', 'Scent 2', 'House', 'EDP', 'Unisex', 'Woody', 'Woody', "
                "'manual')"
            )
        )
