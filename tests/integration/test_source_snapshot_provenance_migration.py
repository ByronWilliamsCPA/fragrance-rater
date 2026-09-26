"""Exercise the SourceSnapshot provenance-fields migration (a3f8c1d9e2b7, ADR-012)."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import JSON as SA_JSON
from sqlalchemy import String as SA_String
from sqlalchemy import column as sa_column
from sqlalchemy import create_engine, inspect, select, table, text
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models import Base

_VERSIONS = Path(__file__).parents[2] / "alembic/versions"
_TABLE = "calibration_source_snapshots"
_NEW_COLUMNS = {"source_type", "permission_state", "fields", "source_reference"}
_NEW_CHECKS = {
    "ck_calibration_source_snapshots_source_type",
    "ck_calibration_source_snapshots_permission_state",
    "ck_calibration_source_snapshots_has_source",
}


def _load_migration(filename: str):
    path = _VERSIONS / filename
    spec = importlib.util.spec_from_file_location(filename, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_migration():
    return _load_migration("a3f8c1d9e2b7_source_snapshot_provenance_fields.py")


def _snapshots_table():
    """A minimal Core handle whose JSON columns round-trip through SQLAlchemy."""
    return table(
        _TABLE,
        sa_column("id", SA_String()),
        sa_column("fragrance_id", SA_String()),
        sa_column("source_type", SA_String()),
        sa_column("permission_state", SA_String()),
        sa_column("fields", SA_JSON()),
        sa_column("source_url", SA_String()),
        sa_column("source_reference", SA_String()),
        sa_column("verification_status", SA_String()),
        sa_column("retrieved_at"),
        sa_column("payload", SA_JSON()),
    )


def _upgrade_to_pre_provenance_schema(connection):
    """Build the schema exactly as it stood right before a3f8c1d9e2b7.

    ``Base.metadata`` reflects the current ORM model, which already declares
    every column and CHECK constraint this migration adds. The immediately
    prior migration (7daf681ed339) never touches ``calibration_source_snapshots``;
    the table's last real definition is ``c731b42e9a01``'s ``create_table``,
    so it is dropped and recreated here with exactly that migration's columns
    (``source_url`` NOT NULL, no provenance columns, no CHECKs). No other
    table references it by foreign key, so the drop is safe.
    """
    Base.metadata.create_all(connection)
    op = Operations(MigrationContext.configure(connection))
    op.drop_table(_TABLE)
    op.execute(
        text(
            "CREATE TABLE calibration_source_snapshots ("
            "id VARCHAR(36) NOT NULL, "
            "fragrance_id VARCHAR(36) NOT NULL, "
            "source_url VARCHAR(1000) NOT NULL, "
            "verification_status VARCHAR(30) NOT NULL, "
            "retrieved_at DATETIME NOT NULL, "
            "payload JSON NOT NULL, "
            "PRIMARY KEY (id), "
            "FOREIGN KEY(fragrance_id) REFERENCES fragrances (id) "
            "ON DELETE RESTRICT)"
        )
    )


def _seed_fragrance(connection) -> None:
    connection.execute(
        text(
            "INSERT INTO fragrances(id, name, brand, concentration, gender_target, "
            "primary_family, subfamily, data_source) VALUES "
            "('f1', 'Scent', 'House', 'EDP', 'Unisex', 'Woody', 'Woody', 'manual')"
        )
    )


def _insert_legacy_snapshot(connection, row_id: str) -> None:
    """Insert a row shaped like a pre-migration ParfumoScraper._save_source write."""
    legacy = table(
        _TABLE,
        sa_column("id", SA_String()),
        sa_column("fragrance_id", SA_String()),
        sa_column("source_url", SA_String()),
        sa_column("verification_status", SA_String()),
        sa_column("retrieved_at"),
        sa_column("payload", SA_JSON()),
    )
    connection.execute(
        legacy.insert().values(
            id=row_id,
            fragrance_id="f1",
            source_url=f"https://www.parfumo.com/Perfumes/House/{row_id}",
            verification_status="unverified",
            retrieved_at="2026-01-01 00:00:00",
            payload={"name": "Scent"},
        )
    )


def _upgraded_connection_setup(connection) -> None:
    _upgrade_to_pre_provenance_schema(connection)
    _seed_fragrance(connection)
    _insert_legacy_snapshot(connection, "legacy-1")
    with Operations.context(MigrationContext.configure(connection)):
        load_migration().upgrade()


def _insert_snapshot(connection, **overrides: object) -> None:
    values: dict[str, object] = {
        "id": "new-1",
        "fragrance_id": "f1",
        "source_type": "manufacturer_provided",
        "permission_state": "retain_and_train",
        "fields": ["concentration"],
        "source_url": None,
        "source_reference": "Email reply from the house, 2026-09-20",
        "verification_status": "unverified",
        "retrieved_at": "2026-09-20 00:00:00",
        "payload": {},
    }
    values.update(overrides)
    connection.execute(_snapshots_table().insert().values(**values))


def _check_names(connection) -> set[str]:
    return {
        c["name"]
        for c in inspect(connection).get_check_constraints(_TABLE)
        if c["name"] is not None
    }


def test_upgrade_backfills_legacy_rows_with_excluded_legacy_provenance():
    """Every pre-existing row gets ADR-012's exact legacy provenance values.

    ``fields`` must read back as a real Python list through SQLAlchemy's JSON
    type. A raw ``CAST(:fields AS JSON)`` backfill stores the integer 0 on
    SQLite (SQLite has no JSON type, so the CAST is a numeric-affinity
    conversion), which this assertion catches.
    """
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgraded_connection_setup(connection)

        snapshots = _snapshots_table()
        row = connection.execute(
            select(
                snapshots.c.source_type,
                snapshots.c.permission_state,
                snapshots.c.fields,
                snapshots.c.source_url,
                snapshots.c.source_reference,
            ).where(snapshots.c.id == "legacy-1")
        ).one()
        assert row.source_type == "excluded_legacy"
        assert row.permission_state == "excluded_no_new_writes"
        assert row.fields == ["concentration", "launch_year", "brand"]
        assert isinstance(row.fields, list)
        assert row.source_url == "https://www.parfumo.com/Perfumes/House/legacy-1"
        assert row.source_reference is None

        stored_type = connection.execute(
            text(
                "SELECT typeof(fields) FROM calibration_source_snapshots "
                "WHERE id = 'legacy-1'"
            )
        ).scalar_one()
        assert stored_type == "text"

        columns = {c["name"]: c for c in inspect(connection).get_columns(_TABLE)}
        assert set(columns) >= _NEW_COLUMNS
        assert columns["source_url"]["nullable"] is True
        assert columns["source_type"]["nullable"] is False
        assert columns["permission_state"]["nullable"] is False
        assert columns["fields"]["nullable"] is False
        assert _check_names(connection) >= _NEW_CHECKS


def test_upgrade_accepts_a_reference_only_row():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgraded_connection_setup(connection)
        _insert_snapshot(connection)

        count = connection.execute(
            text(
                "SELECT COUNT(*) FROM calibration_source_snapshots "
                "WHERE source_url IS NULL"
            )
        ).scalar_one()
        assert count == 1


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"source_type": "parfumo"}, id="invalid-source-type"),
        pytest.param({"permission_state": "anything"}, id="invalid-permission"),
        pytest.param(
            {"source_url": None, "source_reference": None}, id="both-identifiers-null"
        ),
        pytest.param(
            {"source_url": "", "source_reference": None}, id="empty-url-null-ref"
        ),
        pytest.param(
            {"source_url": None, "source_reference": ""}, id="null-url-empty-ref"
        ),
        pytest.param(
            {"source_url": "   ", "source_reference": "  "}, id="whitespace-both"
        ),
    ],
)
def test_upgrade_rejects_invalid_provenance(overrides: dict[str, object]):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgraded_connection_setup(connection)

        with pytest.raises(IntegrityError):
            _insert_snapshot(connection, **overrides)


def test_downgrade_succeeds_when_every_row_has_a_source_url():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgraded_connection_setup(connection)
        _insert_snapshot(
            connection,
            id="new-with-url",
            source_url="https://example.test/house/scent",
            source_reference="Also confirmed by email",
        )

        with Operations.context(MigrationContext.configure(connection)):
            load_migration().downgrade()

        columns = {c["name"]: c for c in inspect(connection).get_columns(_TABLE)}
        assert not (_NEW_COLUMNS & set(columns))
        assert columns["source_url"]["nullable"] is False
        assert not (_NEW_CHECKS & _check_names(connection))

        urls = connection.execute(
            text("SELECT source_url FROM calibration_source_snapshots ORDER BY id")
        ).scalars()
        assert list(urls) == [
            "https://www.parfumo.com/Perfumes/House/legacy-1",
            "https://example.test/house/scent",
        ]


@pytest.mark.parametrize(
    "source_url",
    [
        pytest.param(None, id="null-url"),
        pytest.param("", id="empty-url"),
        pytest.param("   ", id="whitespace-url"),
    ],
)
def test_downgrade_refuses_and_leaves_schema_unchanged_with_reference_only_row(
    source_url: str | None,
):
    """A reference-only row cannot survive the downgrade intact.

    A NULL ``source_url`` would violate the restored NOT NULL; a blank one
    would pass it, but dropping ``source_reference`` would still discard the
    row's only real provenance. Either way, downgrade must fail loudly with an
    operator-actionable RuntimeError before any schema change, not with a raw
    IntegrityError midway through a batch table rebuild (or silently).
    """
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgraded_connection_setup(connection)
        _insert_snapshot(connection, id="reference-only", source_url=source_url)

        with (
            pytest.raises(RuntimeError, match=r"1 calibration_source_snapshots row"),
            Operations.context(MigrationContext.configure(connection)),
        ):
            load_migration().downgrade()

        columns = {c["name"]: c for c in inspect(connection).get_columns(_TABLE)}
        assert set(columns) >= _NEW_COLUMNS
        assert columns["source_url"]["nullable"] is True
        assert _check_names(connection) >= _NEW_CHECKS
        remaining = connection.execute(
            text("SELECT COUNT(*) FROM calibration_source_snapshots")
        ).scalar_one()
        assert remaining == 2
