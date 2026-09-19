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


def load_migration():
    path = _VERSIONS / "7daf681ed339_training_eligibility_lookup.py"
    spec = importlib.util.spec_from_file_location(
        "training_eligibility_migration", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade_to_pre_training_eligibility_schema(connection):
    """Build the schema as it stood right before 7daf681ed339.

    ``Base.metadata`` already reflects the current ORM model, which
    declares ``training_eligibility_code`` and the ``training_eligibilities``
    table, so both are stripped back out here to reproduce the migration's
    own starting state.
    """
    Base.metadata.create_all(connection)
    # The ORM's inline `ForeignKey(...)` leaves the constraint unnamed, so
    # (mirroring test_worn_by_reviewer_migration.py's own helper) the index
    # is dropped by plain SQL first, and dropping the column in batch mode
    # implicitly drops its unnamed FK as part of the table rebuild, rather
    # than trying to `drop_constraint` it by the name the real migration
    # assigns (which only exists once the migration itself has run).
    connection.execute(text("DROP INDEX ix_fragrances_training_eligibility_code"))
    op = Operations(MigrationContext.configure(connection))
    with op.batch_alter_table("fragrances") as batch_op:
        batch_op.drop_column("training_eligibility_code")
    op.drop_table("training_eligibilities")


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
        assert rows[0].display_label == "Eligible for training"


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


def test_downgrade_drops_column_fk_index_and_table():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgrade_to_pre_training_eligibility_schema(connection)
        _seed_fragrance(connection)

        with Operations.context(MigrationContext.configure(connection)):
            load_migration().upgrade()
            load_migration().downgrade()

        columns = {c["name"] for c in inspect(connection).get_columns("fragrances")}
        assert "training_eligibility_code" not in columns

        tables = inspect(connection).get_table_names()
        assert "training_eligibilities" not in tables

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
