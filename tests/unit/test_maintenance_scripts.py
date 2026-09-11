"""Regression tests for repository maintenance scripts."""

from __future__ import annotations

import base64
import importlib.util
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).parents[2]


def load_script(name: str) -> ModuleType:
    """Load a standalone Python script as a module."""
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_type_hint_check_ignores_runtime_bitwise_or() -> None:
    """Runtime bitwise operations do not require deferred annotations."""
    module = load_script("check_type_hints")

    assert module.has_union_pipe_syntax("permissions = READ | WRITE\n") is False
    assert module.has_union_pipe_syntax("value: str | None = None\n") is True


def test_mkdocs_cleanup_preserves_project_documentation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disabling MkDocs removes tooling without deleting authored docs."""
    module = load_script("cleanup_conditional_files")
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    authored = docs / "project-plan.md"
    authored.write_text("keep me", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text("site_name: test", encoding="utf-8")

    module.cleanup_conditional_files({"project_slug": "sample", "use_mkdocs": "no"})

    assert authored.read_text(encoding="utf-8") == "keep me"
    assert not (tmp_path / "mkdocs.yml").exists()


def test_orphan_check_maps_disabled_health_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A disabled health-check feature reports its generated route."""
    module = load_script("check_orphaned_files")
    monkeypatch.chdir(tmp_path)
    health = tmp_path / "src" / "sample" / "api" / "health.py"
    health.parent.mkdir(parents=True)
    health.touch()

    orphaned = module.check_orphaned_files(
        {
            "project_slug": "sample",
            "include_api_framework": "yes",
            "include_health_checks": "no",
        }
    )

    assert ("include_health_checks", "no", Path("src/sample/api/health.py")) in orphaned


def test_assured_oss_credentials_use_restricted_temporary_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Encoded credentials receive an unpredictable owner-only file."""
    module = load_script("validate_assuredoss")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    encoded = base64.b64encode(b'{"type":"service_account"}').decode()
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS_B64", encoded)

    credential_path = module.setup_credentials()
    assert credential_path is not None
    try:
        assert credential_path.name != "gcp-credentials.json"
        if os.name == "posix":
            assert stat.S_IMODE(credential_path.stat().st_mode) == (
                stat.S_IRUSR | stat.S_IWUSR
            )
    finally:
        credential_path.unlink(missing_ok=True)


@pytest.mark.skipif(
    os.name == "nt" or shutil.which("bash") is None,
    reason="the wrapper has POSIX shell semantics",
)
@pytest.mark.parametrize(
    ("cruft_exit", "cleanup_exit", "expected"), [(7, 0, 7), (0, 6, 6)]
)
def test_cruft_wrapper_propagates_failures(
    tmp_path: Path, cruft_exit: int, cleanup_exit: int, expected: int
) -> None:
    """The wrapper fails when either update or cleanup fails."""
    (tmp_path / ".cruft.json").write_text("{}", encoding="utf-8")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "cleanup_conditional_files.py").write_text(
        f"raise SystemExit({cleanup_exit})\n", encoding="utf-8"
    )
    binaries = tmp_path / "bin"
    binaries.mkdir()
    fake_cruft = binaries / "cruft"
    fake_cruft.write_text(f"#!/bin/sh\nexit {cruft_exit}\n", encoding="utf-8")
    fake_cruft.chmod(0o755)

    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(  # noqa: S603
        [bash, str(ROOT / "scripts" / "cruft-update.sh")],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{binaries}{os.pathsep}{os.environ['PATH']}"},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == expected
