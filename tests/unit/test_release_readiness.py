"""Tests for release-evidence validators used by P1."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).parents[2]


def load_script(name: str) -> ModuleType:
    """Load a repository script as a module."""
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_requires_verified_exact_physical_versions() -> None:
    """Unknown versions and unconfirmed samples remain release blocking."""
    validator = load_script("validate_calibration_manifest")
    document = {
        "program_name": "Baseline",
        "program_version": "v1",
        "entries": [
            {
                "membership_key": "m1",
                "fragrance_id": "f1",
                "brand": "House",
                "name": "Scent",
                "concentration": "unknown",
                "version_key": "house-scent-unknown",
                "source_url": "http://example.test/scent",
                "verification_evidence": "page title",
                "physical_sample_confirmed": False,
                "role": "UNIVERSAL_BASELINE",
            }
        ],
    }
    errors = validator.validate_manifest(document)
    assert any("concentration cannot be unknown" in error for error in errors)
    assert any("absolute HTTPS" in error for error in errors)
    assert any("physical_sample_confirmed" in error for error in errors)


def test_manifest_accepts_a_repeat_of_the_same_verified_version() -> None:
    """A hidden repeat is a separate membership for the original version."""
    validator = load_script("validate_calibration_manifest")
    base = {
        "membership_key": "original",
        "fragrance_id": "f1",
        "brand": "House",
        "name": "Scent",
        "concentration": "EDP",
        "version_key": "house-scent-edp",
        "source_url": "https://example.test/scent",
        "verification_evidence": "Bottle and source title agree",
        "physical_sample_confirmed": True,
        "role": "UNIVERSAL_BASELINE",
    }
    repeat = {
        **base,
        "membership_key": "repeat",
        "role": "HIDDEN_REPEAT",
        "repeat_of_membership_key": "original",
    }
    document = {
        "program_name": "Baseline",
        "program_version": "v1",
        "entries": [base, repeat],
    }
    assert validator.validate_manifest(document) == []


def test_production_topology_rejects_direct_backend_port() -> None:
    """A host-published API is an Authentik bypass even when headers are checked."""
    validator = load_script("validate_production_topology")
    config = {
        "services": {
            "app": {
                "ports": [{"published": "8000", "target": 8000}],
                "environment": {
                    "AUTHENTIK_REQUIRED": "true",
                    "DATABASE_URL": "postgresql+asyncpg://app:secret@db/app",
                },
            },
            "frontend": {
                "environment": {"VITE_API_URL": "/api"},
                "networks": {
                    "fragrance_rater-network": None,
                    "reverse-proxy": None,
                },
                "labels": {
                    "traefik.enable": "true",
                    "traefik.http.routers.fragrance-rater.middlewares": "auth@file",
                },
            },
            "db": {},
        }
    }
    assert validator.validate_topology(config) == ["service app publishes a host port"]
