"""Exercise the house_submissions migration (b7e3d91a4c2f) on SQLite."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from fragrance_rater.models import Base

_VERSIONS = Path(__file__).parents[2] / "alembic/versions"
_TABLE = "house_submissions"


def _load_migration():
    filename = "b7e3d91a4c2f_house_submissions.py"
    spec = importlib.util.spec_from_file_location(filename, _VERSIONS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(connection, step):
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        step()


def test_upgrade_matches_model_and_downgrade_removes_table():
    migration = _load_migration()
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _run(connection, migration.upgrade)
        inspector = inspect(connection)
        migrated = {column["name"] for column in inspector.get_columns(_TABLE)}
        modeled = {column.name for column in Base.metadata.tables[_TABLE].columns}
        assert migrated == modeled
        checks = {check["name"] for check in inspector.get_check_constraints(_TABLE)}
        modeled_checks = {
            constraint.name
            for constraint in Base.metadata.tables[_TABLE].constraints
            if constraint.__class__.__name__ == "CheckConstraint"
        }
        assert checks == modeled_checks

        _run(connection, migration.downgrade)
        assert _TABLE not in inspect(connection).get_table_names()
