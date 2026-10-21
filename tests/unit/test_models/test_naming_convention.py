"""Naming-convention and migration-policy guards that need no database (R2).

``tests/integration/test_schema_parity_postgres.py`` proves migrated
PostgreSQL names match the models; these tests prove the model names are
themselves well formed, and pin the deliberate restore-not-downgrade policy
(architecture review D-19) so it cannot regress silently.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.sql.elements import conv

from fragrance_rater.core.database import NAMING_CONVENTION
from fragrance_rater.models import Base

if TYPE_CHECKING:
    from types import ModuleType

    from sqlalchemy.engine import Dialect

VERSIONS_DIR = Path(__file__).resolve().parents[3] / "alembic" / "versions"
PG_MAX_IDENTIFIER = 63

# Revisions whose downgrade refuses outright: rollback is "restore a verified
# pre-upgrade backup", per ADR-010 and alembic/README. Nothing in the chain can
# be downgraded past the earliest of these.
RESTORE_ONLY_REVISIONS = (
    "c731b42e9a01",
    "e4b1c2d3f4a5",
    "9ded7f54996c",
    "72fe56efd128",
)


def _all_names(dialect: Dialect) -> list[tuple[str, str]]:
    preparer = dialect.identifier_preparer
    return [
        (table.name, str(preparer.format_constraint(item)))
        for table in Base.metadata.sorted_tables
        for item in (*table.constraints, *table.indexes)
    ]


def test_metadata_uses_project_naming_convention() -> None:
    """``Base.metadata`` carries the convention migrations rely on."""
    assert dict(Base.metadata.naming_convention) == NAMING_CONVENTION


def test_every_check_constraint_has_a_short_rule_name() -> None:
    """CHECK names come from the convention, never repeat the table prefix.

    A model that passes ``name="ck_<table>_..."`` would render as
    ``ck_<table>_ck_<table>_...``.
    """
    for table in Base.metadata.sorted_tables:
        for constraint in table.constraints:
            if not isinstance(constraint, CheckConstraint):
                continue
            assert isinstance(constraint.name, conv), (table.name, constraint)
            assert constraint.name.startswith(f"ck_{table.name}_")
            assert not constraint.name.startswith(f"ck_{table.name}_ck_"), (
                constraint.name
            )


def test_names_fit_postgresql_and_match_sqlite() -> None:
    """No name needs truncation, so PostgreSQL and SQLite names agree.

    SQLAlchemy shortens a convention name longer than the dialect's identifier
    limit with a hash suffix; SQLite has no such limit, so a truncated name
    would differ between the test engine and production.
    """
    pg_names = _all_names(postgresql.dialect())
    too_long = [name for name in pg_names if len(name[1]) > PG_MAX_IDENTIFIER]
    assert not too_long
    assert pg_names == _all_names(sqlite.dialect())


def test_names_are_unique_per_schema() -> None:
    """PostgreSQL index and constraint names share one namespace per schema."""
    names = [name for _, name in _all_names(postgresql.dialect())]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates


def _load_revision(revision: str) -> ModuleType:
    (path,) = VERSIONS_DIR.glob(f"{revision}_*.py")
    spec = importlib.util.spec_from_file_location(f"_rev_{revision}", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("revision", RESTORE_ONLY_REVISIONS)
def test_restore_only_revisions_refuse_downgrade(revision: str) -> None:
    """Each restore-only revision raises before touching the schema (D-19)."""
    module = _load_revision(revision)
    with pytest.raises(RuntimeError, match="backup"):
        module.downgrade()
