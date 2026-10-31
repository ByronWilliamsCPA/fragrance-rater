"""The production override runs the scheduled backup safely (R14, D-18)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader that tolerates Compose's ``!reset`` and ``!override`` tags."""


for _tag in ("!reset", "!override"):
    _ComposeLoader.add_constructor(
        _tag,
        lambda loader, node: (
            loader.construct_sequence(node)
            if isinstance(node, yaml.SequenceNode)
            else loader.construct_scalar(node)
        ),
    )


def _prod() -> dict[str, Any]:
    text = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    return yaml.load(text, Loader=_ComposeLoader)  # noqa: S506 - SafeLoader subclass


def test_the_backup_service_runs_the_script_in_the_postgres_image() -> None:
    backup = _prod()["services"]["backup"]

    assert backup["image"].startswith("postgres:16")
    assert "/scripts/backup_database.sh backup" in backup["command"][0]
    assert (
        "./scripts/backup_database.sh:/scripts/backup_database.sh:ro"
        in backup["volumes"]
    )
    assert (ROOT / "scripts" / "backup_database.sh").is_file()


def test_backups_go_to_a_named_volume_not_the_container_layer() -> None:
    document = _prod()
    backup = document["services"]["backup"]

    assert "backups:/backups" in backup["volumes"]
    assert backup["environment"]["BACKUP_DIR"] == "/backups"
    assert "backups" in document["volumes"]


def test_the_backup_service_is_private_and_reaches_only_the_database() -> None:
    backup = _prod()["services"]["backup"]

    assert "ports" not in backup
    assert backup["networks"] == ["fragrance_rater-network"]
    assert "network_mode" not in backup
    assert backup["depends_on"]["db"]["condition"] == "service_healthy"


def test_the_database_password_is_required_not_defaulted() -> None:
    backup = _prod()["services"]["backup"]

    assert backup["environment"]["PGPASSWORD"].startswith("${DB_PASSWORD:?")


def test_a_stalled_backup_makes_the_service_unhealthy() -> None:
    health = _prod()["services"]["backup"]["healthcheck"]

    assert health["test"][-1] == "check"
    assert "backup_database.sh" in " ".join(health["test"])
    assert health["interval"] == "1h"


def test_the_schedule_and_retention_are_configurable_with_safe_defaults() -> None:
    environment = _prod()["services"]["backup"]["environment"]

    assert environment["BACKUP_INTERVAL_HOURS"] == "${BACKUP_INTERVAL_HOURS:-24}"
    assert environment["BACKUP_RETENTION_DAYS"] == "${BACKUP_RETENTION_DAYS:-14}"
    assert environment["BACKUP_KEEP_MIN"] == "${BACKUP_KEEP_MIN:-3}"
    assert environment["BACKUP_MAX_AGE_HOURS"] == "${BACKUP_MAX_AGE_HOURS:-30}"


def test_the_shipped_backup_service_satisfies_the_topology_validator() -> None:
    """The validator must accept what the production override really ships."""
    path = ROOT / "scripts" / "validate_production_topology.py"
    spec = importlib.util.spec_from_file_location("validate_production_topology", path)
    assert spec is not None
    assert spec.loader is not None
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)

    assert validator._backup_errors(_prod()["services"]["backup"]) == []
