"""Exercise the additive upgrade with populated previous-head tables."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from fragrance_rater.models import Base


def load_migration():
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/c731b42e9a01_controlled_calibration.py"
    )
    spec = importlib.util.spec_from_file_location("calibration_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_preserves_existing_ids_and_allows_dated_encounters():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        Base.metadata.create_all(
            connection,
            tables=[
                t
                for t in Base.metadata.sorted_tables
                if not t.name.startswith("calibration_")
            ],
        )
        connection.execute(text("DROP INDEX uq_fragrance_version"))
        connection.execute(text("ALTER TABLE fragrances DROP COLUMN version_key"))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX uq_fragrance_name_brand ON fragrances(name, brand) WHERE deleted_at IS NULL"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX uq_evaluation_reviewer_fragrance ON evaluations(reviewer_id, fragrance_id) WHERE deleted_at IS NULL"
            )
        )
        connection.execute(
            text("INSERT INTO reviewers(id,name) VALUES ('r','Evaluator')")
        )
        connection.execute(
            text(
                "INSERT INTO fragrances(id,name,brand,concentration,gender_target,primary_family,subfamily,data_source) VALUES ('f','Scent','House','EDP','Unisex','Woody','Woody','manual')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO evaluations(id,fragrance_id,reviewer_id,rating) VALUES ('e','f','r',4)"
            )
        )
        with Operations.context(MigrationContext.configure(connection)):
            load_migration().upgrade()
        assert connection.execute(text("SELECT id,rating FROM evaluations")).all() == [
            ("e", 4)
        ]
        connection.execute(
            text(
                "INSERT INTO evaluations(id,fragrance_id,reviewer_id,rating) VALUES ('e2','f','r',2)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO fragrances(id,name,brand,concentration,gender_target,primary_family,subfamily,data_source) VALUES ('f2','Scent','House','EDT','Unisex','Woody','Woody','manual')"
            )
        )
        assert (
            connection.execute(text("SELECT COUNT(*) FROM evaluations")).scalar() == 2
        )
        assert "calibration_observations" in inspect(connection).get_table_names()
        assert (
            connection.execute(
                text("SELECT version_key FROM fragrances WHERE id='f'")
            ).scalar()
            == "legacy"
        )


def test_lossy_downgrade_is_refused():
    with pytest.raises(RuntimeError, match="backup"):
        load_migration().downgrade()
