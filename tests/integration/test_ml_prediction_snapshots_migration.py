"""Exercise the calibration_observations typing and prediction_snapshots migrations."""

import importlib.util
import logging
import math
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


def _load_migration(filename: str):
    path = _VERSIONS / filename
    spec = importlib.util.spec_from_file_location(filename, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_calibration_migration():
    return _load_migration("c731b42e9a01_controlled_calibration.py")


def load_typing_migration():
    return _load_migration("9ded7f54996c_ml_prediction_snapshots.py")


def load_prediction_snapshots_migration():
    return _load_migration("72fe56efd128_create_prediction_snapshots_table.py")


def _observations_table():
    """A minimal Core handle for inserting legacy pre-upgrade rows."""
    return table(
        "calibration_observations",
        sa_column("id", SA_String()),
        sa_column("presentation_id", SA_String()),
        sa_column("stage", SA_String()),
        sa_column("phase", SA_String()),
        sa_column("elapsed_minutes"),
        sa_column("recorded_by", SA_String()),
        sa_column("created_at"),
        sa_column("responses", SA_JSON()),
    )


def _upgrade_to_pre_typing_schema(connection):
    """Build the schema exactly as it stood right before 9ded7f54996c.

    ``Base.metadata`` reflects the current ORM models (post-``c731b42e9a01``
    fragrances/evaluations shape), so it must be rolled back to that
    migration's *pre*-upgrade expectations first, exactly as
    ``tests/integration/test_calibration_migration.py`` does for the same
    migration.
    """
    Base.metadata.create_all(
        connection,
        tables=[
            t
            for t in Base.metadata.sorted_tables
            if not t.name.startswith("calibration_")
            and t.name != "prediction_snapshots"
        ],
    )
    connection.execute(text("DROP INDEX uq_fragrance_version"))
    connection.execute(text("ALTER TABLE fragrances DROP COLUMN version_key"))
    connection.execute(
        text(
            "CREATE UNIQUE INDEX uq_fragrance_name_brand ON fragrances(name, brand) "
            "WHERE deleted_at IS NULL"
        )
    )
    connection.execute(
        text(
            "CREATE UNIQUE INDEX uq_evaluation_reviewer_fragrance ON "
            "evaluations(reviewer_id, fragrance_id) WHERE deleted_at IS NULL"
        )
    )
    with Operations.context(MigrationContext.configure(connection)):
        load_calibration_migration().upgrade()


def _insert_legacy_row(connection, row_id: str, responses: dict[str, object]) -> None:
    observations = _observations_table()
    connection.execute(
        observations.insert().values(
            id=row_id,
            presentation_id="unused-presentation",
            stage="blotter",
            phase="opening",
            elapsed_minutes=0,
            recorded_by="tester",
            created_at="2026-01-01T00:00:00",
            responses=responses,
        )
    )


def test_upgrade_backfills_valid_values_and_drops_responses():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgrade_to_pre_typing_schema(connection)
        _insert_legacy_row(
            connection,
            "obs-valid",
            {
                "confidence": 3,
                "would_wear": 9,
                "longevity_minutes": 240,
                "likes": "warm and cozy",
                "perceived_notes": ["vanilla", "amber"],
            },
        )

        with Operations.context(MigrationContext.configure(connection)):
            load_typing_migration().upgrade()

        columns = {
            c["name"]
            for c in inspect(connection).get_columns("calibration_observations")
        }
        assert "responses" not in columns
        assert {"confidence", "would_wear", "longevity_minutes", "likes"} <= columns

        row = connection.execute(
            select(
                sa_column("confidence"),
                sa_column("would_wear"),
                sa_column("longevity_minutes"),
                sa_column("likes"),
                sa_column("perceived_notes", SA_JSON()),
            ).select_from(table("calibration_observations"))
        ).one()
        assert row.confidence == 3
        assert row.would_wear == 9
        assert row.longevity_minutes == 240
        assert row.likes == "warm and cozy"
        assert row.perceived_notes == ["vanilla", "amber"]


def test_upgrade_quarantines_out_of_range_value(caplog):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgrade_to_pre_typing_schema(connection)
        _insert_legacy_row(connection, "obs-outrange", {"would_wear": 15})

        with (
            caplog.at_level(logging.WARNING),
            Operations.context(MigrationContext.configure(connection)),
        ):
            load_typing_migration().upgrade()

        would_wear = connection.execute(
            select(sa_column("would_wear")).select_from(
                table("calibration_observations")
            )
        ).scalar_one()
        assert would_wear is None
        assert any("outside" in record.message for record in caplog.records)
        assert any(
            "Quarantined" in record.message
            and "columns during backfill" in record.message
            for record in caplog.records
        )


def test_upgrade_quarantines_non_integer_in_range_float():
    """A legacy in-range float (e.g. 4.7) must be quarantined, never truncated."""
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgrade_to_pre_typing_schema(connection)
        _insert_legacy_row(connection, "obs-nonint", {"would_wear": 4.7})

        with Operations.context(MigrationContext.configure(connection)):
            load_typing_migration().upgrade()

        would_wear = connection.execute(
            select(sa_column("would_wear")).select_from(
                table("calibration_observations")
            )
        ).scalar_one()
        assert would_wear is None, "a non-integer legacy float must never be truncated"


def test_upgrade_quarantines_infinite_value_without_crashing():
    """A legacy float('inf') in the unbounded longevity_minutes column must not crash."""
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgrade_to_pre_typing_schema(connection)
        _insert_legacy_row(connection, "obs-inf", {"longevity_minutes": float("inf")})

        with Operations.context(MigrationContext.configure(connection)):
            load_typing_migration().upgrade()  # must not raise OverflowError

        longevity_minutes = connection.execute(
            select(sa_column("longevity_minutes")).select_from(
                table("calibration_observations")
            )
        ).scalar_one()
        assert longevity_minutes is None


def test_typed_columns_reject_out_of_range_values_after_upgrade():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgrade_to_pre_typing_schema(connection)
        with Operations.context(MigrationContext.configure(connection)):
            load_typing_migration().upgrade()

        observations = table(
            "calibration_observations",
            sa_column("id", SA_String()),
            sa_column("presentation_id", SA_String()),
            sa_column("stage", SA_String()),
            sa_column("phase", SA_String()),
            sa_column("elapsed_minutes"),
            sa_column("recorded_by", SA_String()),
            sa_column("created_at"),
            sa_column("would_wear"),
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                observations.insert().values(
                    id="obs-bad",
                    presentation_id="unused",
                    stage="blotter",
                    phase="opening",
                    elapsed_minutes=0,
                    recorded_by="tester",
                    created_at="2026-01-01T00:00:00",
                    would_wear=999,
                )
            )


def test_typing_migration_downgrade_is_refused():
    with pytest.raises(RuntimeError, match="backup"):
        load_typing_migration().downgrade()


def test_prediction_snapshots_migration_down_revision_points_at_typing_migration():
    assert load_prediction_snapshots_migration().down_revision == "9ded7f54996c"


def test_prediction_snapshots_table_is_created_with_constraints():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _upgrade_to_pre_typing_schema(connection)
        with Operations.context(MigrationContext.configure(connection)):
            load_typing_migration().upgrade()
            load_prediction_snapshots_migration().upgrade()

        columns = {
            c["name"] for c in inspect(connection).get_columns("prediction_snapshots")
        }
        assert {
            "id",
            "reviewer_id",
            "fragrance_id",
            "predicted_rating",
            "outcome_evaluation_id",
            "outcome_observation_id",
            "outcome_linked_at",
        } <= columns

        snapshots = table(
            "prediction_snapshots",
            sa_column("id", SA_String()),
            sa_column("reviewer_id", SA_String()),
            sa_column("fragrance_id", SA_String()),
            sa_column("model_id", SA_String()),
            sa_column("model_version", SA_String()),
            sa_column("input_manifest", SA_JSON()),
            sa_column("created_at"),
            sa_column("predicted_rating"),
        )
        # Non-finite predicted_rating must be rejected by the DB-level check.
        with pytest.raises(IntegrityError):
            connection.execute(
                snapshots.insert().values(
                    id="pred-bad",
                    reviewer_id="r",
                    fragrance_id="f",
                    model_id="m",
                    model_version="1",
                    input_manifest=[],
                    created_at="2026-01-01T00:00:00",
                    predicted_rating=math.inf,
                )
            )


def test_prediction_snapshots_migration_downgrade_is_refused():
    with pytest.raises(RuntimeError, match="backup"):
        load_prediction_snapshots_migration().downgrade()
