"""Exercise the catalog/house alignment migration (c5a9e2d7f1b4) on SQLite.

The full migration chain does not run on SQLite (88627796b194 alters
constraints outside batch mode), so, like the other per-migration tests, this
starts from the model's schema, applies this migration's downgrade to reach
the prior state, then upgrades and compares against the model.
"""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import CheckConstraint, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models import Base

_VERSIONS = Path(__file__).parents[2] / "alembic/versions"


def _migration():
    filename = "c5a9e2d7f1b4_catalog_house_alignment.py"
    spec = importlib.util.spec_from_file_location(filename, _VERSIONS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(connection, step):
    with Operations.context(MigrationContext.configure(connection)):
        step()


def _checks(inspector, table):
    return {
        check["name"]: " ".join(check["sqltext"].split())
        for check in inspector.get_check_constraints(table)
    }


def _modeled_checks(table):
    return {
        constraint.name: " ".join(str(constraint.sqltext).split())
        for constraint in Base.metadata.tables[table].constraints
        if isinstance(constraint, CheckConstraint)
    }


def _version_index_sql(connection):
    return connection.execute(
        text("SELECT sql FROM sqlite_master WHERE name = 'uq_fragrance_version'")
    ).scalar_one()


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migrate.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        _run(connection, _migration().downgrade)
    return engine


def test_downgrade_reaches_the_prior_schema(engine):
    inspector = inspect(engine)
    assert "fragrance_gtins" not in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("fragrances")}
    assert not {"line", "market_status"} & columns
    assert "ck_fragrances_market_status" not in _checks(inspector, "fragrances")
    with engine.connect() as connection:
        assert "deleted_at IS NULL" in _version_index_sql(connection)


def test_upgrade_matches_model_and_keeps_version_index(engine):
    with engine.begin() as connection:
        _run(connection, _migration().upgrade)
    inspector = inspect(engine)
    for table in ("fragrances", "fragrance_gtins"):
        assert {c["name"] for c in inspector.get_columns(table)} == {
            c.name for c in Base.metadata.tables[table].columns
        }
        assert _checks(inspector, table) == _modeled_checks(table)
    assert {
        fk["referred_table"] for fk in inspector.get_foreign_keys("fragrance_gtins")
    } == {
        "fragrances",
        "calibration_source_snapshots",
    }
    # The batch rebuild of `fragrances` must keep the partial unique index that
    # keeps live versions distinct.
    with engine.connect() as connection:
        assert "deleted_at IS NULL" in _version_index_sql(connection)


def test_market_status_check_rejects_unknown_values(engine):
    with engine.begin() as connection:
        _run(connection, _migration().upgrade)
    insert = text(
        "INSERT INTO fragrances (id, name, brand, concentration, version_key, "
        "gender_target, primary_family, subfamily, data_source, created_at, "
        "updated_at, market_status) VALUES (:id, 'N', 'B', 'EDP', 'legacy', "
        "'Unisex', 'Woody', 'Dry Woods', 'manual', CURRENT_TIMESTAMP, "
        "CURRENT_TIMESTAMP, :status)"
    )
    with engine.begin() as connection:
        connection.execute(insert, {"id": "ok", "status": "discontinued"})
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert, {"id": "bad", "status": "sold_out"})
