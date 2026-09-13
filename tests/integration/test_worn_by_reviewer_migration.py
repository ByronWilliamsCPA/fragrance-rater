"""Exercise the worn_by_reviewer_id migration (da7c14f4a129)."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models import Base

_VERSIONS = Path(__file__).parents[2] / "alembic/versions"


def load_migration():
    path = _VERSIONS / "da7c14f4a129_add_worn_by_reviewer_id_to_evaluations.py"
    spec = importlib.util.spec_from_file_location("worn_by_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade_to_pre_worn_by_schema(connection):
    """Build the schema exactly as it stood right before da7c14f4a129.

    ``Base.metadata`` reflects the current ORM model, which already declares
    ``worn_by_reviewer_id`` and its CHECK constraint, so both are stripped
    back out here (index, CHECK, foreign key, column, in that order, the
    reverse of how the migration adds them) to reproduce the migration's own
    starting state.
    """
    Base.metadata.create_all(connection)
    connection.execute(text("DROP INDEX ix_evaluations_worn_by_reviewer_id"))
    # SQLite has no ALTER TABLE ... DROP CONSTRAINT; rebuild via batch mode,
    # mirroring the migration's own use of batch_alter_table. Batch mode
    # drops the unnamed FK that references the column automatically when
    # the column is dropped, but a named CHECK constraint (this one mirrors
    # the migration's name at the ORM level, see models/evaluation.py) must
    # be dropped explicitly or it survives the table rebuild dangling.
    op = Operations(MigrationContext.configure(connection))
    with op.batch_alter_table("evaluations") as batch_op:
        batch_op.drop_constraint(
            "ck_evaluations_worn_by_reviewer_not_self", type_="check"
        )
        batch_op.drop_column("worn_by_reviewer_id")


def _seed_reviewers(connection) -> None:
    connection.execute(
        text("INSERT INTO reviewers(id, name) VALUES ('alice', 'Alice')")
    )
    connection.execute(text("INSERT INTO reviewers(id, name) VALUES ('bob', 'Bob')"))
    connection.execute(
        text(
            "INSERT INTO fragrances(id, name, brand, concentration, gender_target, "
            "primary_family, subfamily, data_source) VALUES "
            "('f1', 'Scent', 'House', 'EDP', 'Unisex', 'Woody', 'Woody', 'manual')"
        )
    )


def test_upgrade_adds_column_index_fk_and_check_constraint():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgrade_to_pre_worn_by_schema(connection)
        _seed_reviewers(connection)

        with Operations.context(MigrationContext.configure(connection)):
            load_migration().upgrade()

        columns = {c["name"] for c in inspect(connection).get_columns("evaluations")}
        assert "worn_by_reviewer_id" in columns

        indexes = {i["name"] for i in inspect(connection).get_indexes("evaluations")}
        assert "ix_evaluations_worn_by_reviewer_id" in indexes

        fks = inspect(connection).get_foreign_keys("evaluations")
        assert any(
            fk["constrained_columns"] == ["worn_by_reviewer_id"]
            and fk["referred_table"] == "reviewers"
            for fk in fks
        )

        # NULL worn_by_reviewer_id ("on me") is always allowed.
        connection.execute(
            text(
                "INSERT INTO evaluations(id, fragrance_id, reviewer_id, rating) "
                "VALUES ('e-self', 'f1', 'alice', 4)"
            )
        )
        # A different worn_by_reviewer_id ("on others") is allowed.
        connection.execute(
            text(
                "INSERT INTO evaluations"
                "(id, fragrance_id, reviewer_id, rating, worn_by_reviewer_id) "
                "VALUES ('e-other', 'f1', 'alice', 4, 'bob')"
            )
        )
        # worn_by_reviewer_id == reviewer_id must be rejected at the DB level.
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO evaluations"
                    "(id, fragrance_id, reviewer_id, rating, worn_by_reviewer_id) "
                    "VALUES ('e-bad', 'f1', 'alice', 4, 'alice')"
                )
            )


def test_downgrade_drops_check_constraint_fk_index_and_column():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgrade_to_pre_worn_by_schema(connection)
        _seed_reviewers(connection)

        with Operations.context(MigrationContext.configure(connection)):
            load_migration().upgrade()
            load_migration().downgrade()

        columns = {c["name"] for c in inspect(connection).get_columns("evaluations")}
        assert "worn_by_reviewer_id" not in columns

        # The self-reference rule is gone with the column, so a plain rating
        # insert (no worn_by_reviewer_id to violate) still succeeds.
        connection.execute(
            text(
                "INSERT INTO evaluations(id, fragrance_id, reviewer_id, rating) "
                "VALUES ('e-after-downgrade', 'f1', 'alice', 4)"
            )
        )
