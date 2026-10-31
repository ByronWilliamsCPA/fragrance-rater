"""The production override passes the secrets the app needs (S-04, S-16, S-28)."""

from __future__ import annotations

import re
from pathlib import Path

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


def _load(file: str) -> dict:
    return yaml.load((ROOT / file).read_text(encoding="utf-8"), Loader=_ComposeLoader)  # noqa: S506 - SafeLoader subclass


def _service_environment(file: str, service: str) -> dict[str, str]:
    return _load(file)["services"][service]["environment"]


def test_the_production_override_requires_both_billed_endpoint_secrets() -> None:
    """Neither compose file has an env_file, so unnamed variables never arrive."""
    environment = _service_environment("docker-compose.prod.yml", "app")

    for name in ("FRAGRANCE_RATER_API_KEY", "OPENROUTER_API_KEY"):
        # ``${NAME:?message}``: Compose refuses to render when it is unset.
        assert re.fullmatch(rf"\$\{{{name}:\?.+\}}", environment[name]), name


def test_no_compose_file_declares_an_env_file_that_would_hide_the_requirement() -> None:
    for file in ("docker-compose.yml", "docker-compose.prod.yml"):
        for name, service in _load(file)["services"].items():
            assert "env_file" not in service, f"{file}:{name}"


def test_env_example_ships_no_literal_database_password() -> None:
    """A weak default would defeat the ${DB_PASSWORD:?} guard (S-16)."""
    active = [
        line
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line.startswith(("DATABASE_URL=", "DB_PASSWORD="))
    ]

    assert active == []


def test_the_documented_model_override_reaches_the_app_with_the_settings_default() -> (
    None
):
    """``OPENROUTER_MODEL`` in ``.env`` only matters if Compose passes it on."""
    from fragrance_rater.core.config import Settings

    default = Settings.model_fields["openrouter_model"].default
    environment = _service_environment("docker-compose.yml", "app")

    assert environment["OPENROUTER_MODEL"] == f"${{OPENROUTER_MODEL:-{default}}}"


def test_env_example_ships_no_placeholder_secret_as_an_active_setting() -> None:
    """A copied-verbatim placeholder would become a working credential."""
    secrets = re.compile(
        r"^(FRAGRANCE_RATER_API_KEY|OPENROUTER_API_KEY)=\s*\S", re.MULTILINE
    )

    assert secrets.search((ROOT / ".env.example").read_text(encoding="utf-8")) is None


def test_the_replica_comment_matches_the_override_default() -> None:
    """The base file said default 2 while the override defaults to 1 (S-28)."""
    base = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    prod = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    assert "deploy.replicas (default 2)" not in base
    assert "replicas: ${REPLICAS:-1}" in prod
