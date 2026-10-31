"""``scripts/verify_restore.py``: the parts that need no database (R14, D-18)."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

pytestmark = pytest.mark.unit

if TYPE_CHECKING:
    from types import ModuleType

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def load() -> ModuleType:
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "verify_restore", SCRIPTS / "verify_restore.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load()


def test_connection_details_travel_in_environment_variables() -> None:
    env = tool.connection_environment(
        "postgresql://admin:s3cret@db.internal:5433/postgres"
    )

    assert env == {
        "PGHOST": "db.internal",
        "PGPORT": "5433",
        "PGUSER": "admin",
        "PGPASSWORD": "s3cret",
        "PGDATABASE": "postgres",
    }


def test_a_password_with_special_characters_is_decoded() -> None:
    env = tool.connection_environment("postgresql://admin:p%40ss%2Fw%3Ard@db/postgres")

    assert env["PGPASSWORD"] == "p@ss/w:rd"


def test_the_database_can_be_overridden_and_defaults_sensibly() -> None:
    assert (
        tool.connection_environment("postgresql://u:p@h/live", "scratch")["PGDATABASE"]
        == "scratch"
    )
    assert tool.connection_environment("postgresql://u:p@h")["PGDATABASE"] == "postgres"
    assert "PGPORT" not in tool.connection_environment("postgresql://u:p@h/x")


@pytest.mark.parametrize(
    "url", ["sqlite:///x.db", "postgresql+asyncpg://u:p@h/x", "not a url", ""]
)
def test_only_postgresql_urls_are_accepted(url: str) -> None:
    with pytest.raises(tool.RestoreError, match="postgresql://"):
        tool.connection_environment(url)


def test_the_database_url_can_point_elsewhere() -> None:
    assert (
        tool.database_url("postgresql://u:p@h:5432/postgres", "scratch")
        == "postgresql://u:p@h:5432/scratch"
    )


def test_scratch_names_are_unique_and_safe_to_quote() -> None:
    names = {tool.scratch_name() for _ in range(50)}

    assert len(names) == 50
    assert all(
        re.fullmatch(r"restore_verify_[0-9]{8}t[0-9]{6}z_[0-9a-f]{6}", name)
        for name in names
    )
    assert tool.scratch_name(datetime(2026, 10, 31, 2, 0, 0, tzinfo=UTC)).startswith(
        "restore_verify_20261031t020000z_"
    )


def test_a_matching_sidecar_is_confirmed(tmp_path: Path) -> None:
    dump = tmp_path / "fragrance_rater-20261031T020000Z.dump"
    dump.write_bytes(b"contents")
    (tmp_path / f"{dump.name}.sha256").write_text(
        f"{tool.sha256_of(dump)}  {dump.name}\n"
    )

    assert tool.check_checksum(dump) is True


def test_a_differing_sidecar_is_a_mismatch(tmp_path: Path) -> None:
    dump = tmp_path / "fragrance_rater-20261031T020000Z.dump"
    dump.write_bytes(b"contents")
    (tmp_path / f"{dump.name}.sha256").write_text(f"{'0' * 64}  {dump.name}\n")

    assert tool.check_checksum(dump) is False


def test_a_missing_sidecar_is_unknown_not_a_pass(tmp_path: Path) -> None:
    dump = tmp_path / "fragrance_rater-20261031T020000Z.dump"
    dump.write_bytes(b"contents")

    assert tool.check_checksum(dump) is None


def test_the_backup_time_comes_from_its_name_else_its_mtime(tmp_path: Path) -> None:
    named = tmp_path / "fragrance_rater-20261031T020304Z.dump"
    named.write_bytes(b"x")
    plain = tmp_path / "manual.dump"
    plain.write_bytes(b"x")
    os.utime(plain, (1_700_000_000, 1_700_000_000))

    assert tool.backup_created_at(named) == datetime(2026, 10, 31, 2, 3, 4, tzinfo=UTC)
    assert tool.backup_created_at(plain) == datetime.fromtimestamp(
        1_700_000_000, tz=UTC
    )


def test_the_evidence_keeps_counts_and_never_row_content() -> None:
    summary = tool.summarize(
        {
            "alembic_version": "f74bf7ff9c2d",
            "row_counts": {"fragrances": 3},
            "duplicate_natural_keys": {"Secret House|Secret Name": 2},
            "hashes": {"fragrances": {"id": "abc"}},
        }
    )

    assert summary == {
        "alembic_version": "f74bf7ff9c2d",
        "row_counts": {"fragrances": 3},
    }


@pytest.mark.parametrize("body", [None, b""])
def test_a_missing_or_empty_backup_is_a_tool_failure(
    tmp_path: Path, body: bytes | None
) -> None:
    backup = tmp_path / "fragrance_rater-20261031T020000Z.dump"
    if body is not None:
        backup.write_bytes(body)

    with pytest.raises(tool.RestoreError, match="missing or empty"):
        tool._inspect_backup(backup)


def _main(monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["verify_restore.py", *argv])
    return tool.main()


def test_main_needs_the_admin_url_in_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("P1_ADMIN_DATABASE_URL", raising=False)

    code = _main(monkeypatch, "--backup", str(tmp_path / "x.dump"))

    assert code == 2
    assert "P1_ADMIN_DATABASE_URL" in capsys.readouterr().err


def test_main_rejects_an_unreadable_source_inventory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("P1_ADMIN_DATABASE_URL", "postgresql://u:p@h/postgres")
    bad = tmp_path / "inv.json"
    bad.write_text("[1, 2")
    not_object = tmp_path / "list.json"
    not_object.write_text("[1]")

    assert _main(monkeypatch, "--backup", "x.dump", "--source-inventory", str(bad)) == 2
    assert (
        _main(
            monkeypatch,
            "--backup",
            "x.dump",
            "--source-inventory",
            str(tmp_path / "none"),
        )
        == 2
    )
    assert (
        _main(monkeypatch, "--backup", "x.dump", "--source-inventory", str(not_object))
        == 2
    )
    assert "not an inventory object" in capsys.readouterr().err


def _evidence(**overrides: Any) -> dict[str, Any]:
    return {
        "verified": True,
        "backup_file": "fragrance_rater-20261031T020000Z.dump",
        "checksum_matches_sidecar": True,
        "backup_age_seconds": 120,
        "restore_seconds": 1.5,
        "violations": [],
        **overrides,
    }


@pytest.mark.parametrize(
    ("overrides", "code", "message"),
    [
        ({}, 0, ""),
        (
            {"verified": False, "checksum_matches_sidecar": False},
            1,
            "does not match its checksum",
        ),
        (
            {"verified": False, "violations": ["fragrances rows differ"]},
            1,
            "fragrances rows differ",
        ),
    ],
)
def test_main_maps_the_evidence_to_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    overrides: dict[str, Any],
    code: int,
    message: str,
) -> None:
    async def fake_verify(*_: object) -> dict[str, Any]:
        return _evidence(**overrides)

    monkeypatch.setenv("P1_ADMIN_DATABASE_URL", "postgresql://u:p@h/postgres")
    monkeypatch.setattr(tool, "verify", fake_verify)
    output = tmp_path / "evidence.json"

    assert _main(monkeypatch, "--backup", "x.dump", "--output", str(output)) == code
    captured = capsys.readouterr()
    assert message in captured.err
    if code == 0:
        assert "Verified:" in captured.out
    assert json.loads(output.read_text())["backup_file"].endswith(".dump")


def test_main_reports_a_restore_failure_as_a_tool_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def failing(*_: object) -> dict[str, Any]:
        message = "pg_restore failed (exit 1): boom"
        raise tool.RestoreError(message)

    monkeypatch.setenv("P1_ADMIN_DATABASE_URL", "postgresql://u:p@h/postgres")
    monkeypatch.setattr(tool, "verify", failing)

    assert _main(monkeypatch, "--backup", "x.dump") == 2
    assert "pg_restore failed" in capsys.readouterr().err


def test_main_reports_an_unwritable_output_as_a_tool_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def fake_verify(*_: object) -> dict[str, Any]:
        return _evidence()

    monkeypatch.setenv("P1_ADMIN_DATABASE_URL", "postgresql://u:p@h/postgres")
    monkeypatch.setattr(tool, "verify", fake_verify)

    assert (
        _main(
            monkeypatch,
            "--backup",
            "x.dump",
            "--output",
            str(tmp_path / "no" / "e.json"),
        )
        == 2
    )
