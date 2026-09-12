"""Tests for release-evidence validators used by P1."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

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


def test_manifest_reports_non_string_identifiers_without_crashing() -> None:
    """Structured identifiers are validation errors rather than unhashable keys."""
    validator = load_script("validate_calibration_manifest")
    document = {
        "program_name": "Baseline",
        "program_version": "v1",
        "entries": [
            {
                "membership_key": ["bad"],
                "fragrance_id": {"bad": "id"},
                "brand": "House",
                "name": "Scent",
                "concentration": "EDP",
                "version_key": "house-scent-edp",
                "source_url": "https://example.test/scent",
                "verification_evidence": "Bottle and source title agree",
                "physical_sample_confirmed": True,
                "role": "UNIVERSAL_BASELINE",
            }
        ],
    }
    errors = validator.validate_manifest(document)
    assert "entries[0].membership_key must be non-empty text" in errors
    assert "entries[0].fragrance_id must be non-empty text" in errors


def valid_p6_readiness() -> dict[str, Any]:
    """Return a complete machine-readable P6 go record."""
    return {
        "release": {
            "commit": "a" * 40,
            "app_image_digest": f"sha256:{'b' * 64}",
            "frontend_image_digest": f"sha256:{'c' * 64}",
            "deployment_reference": "private:release-candidate",
            "remote_ci_passed": True,
        },
        "gates": {f"P6.{index}": "pass" for index in range(1, 7)},
        "artifacts": {
            "p1_gate": "private:p1",
            "device_matrix": "private:devices",
            "synthetic_rehearsal": "private:rehearsal",
            "redacted_export_manifest": "private:export",
            "quality_report": "private:quality",
            "operations_drill": "private:operations",
            "signed_decision": "private:decision",
        },
        "known_limitations": [],
        "decision": {
            "value": "go",
            "decided_by": "core maintainer",
            "decided_at": "2026-09-12T04:00:00Z",
        },
    }


def test_p6_readiness_accepts_a_complete_go_record() -> None:
    """All gates, evidence references, and immutable release fields close P6."""
    validator = load_script("validate_p6_readiness")
    assert validator.validate_readiness(valid_p6_readiness()) == []


def test_p6_readiness_rejects_pending_evidence_and_decision() -> None:
    """A partially filled template cannot authorize actual perfume testing."""
    validator = load_script("validate_p6_readiness")
    document = valid_p6_readiness()
    document["release"]["remote_ci_passed"] = False
    document["gates"]["P6.4"] = "pending"
    document["artifacts"]["quality_report"] = "replace-with-private-reference"
    document["decision"]["value"] = "no-go"
    errors = validator.validate_readiness(document)
    assert "release.remote_ci_passed must be true" in errors
    assert "gates.P6.4 must be pass" in errors
    assert (
        "artifacts.quality_report must use the private:<opaque-reference> format"
        in errors
    )
    assert "decision.value must be go to close P6" in errors


def valid_limitation() -> dict[str, Any]:
    """Return a complete, well-formed, non-blocking known limitation."""
    return {
        "id": "P6-L1",
        "summary": "Participant disclosure failure",
        "affected_role": "participant",
        "workflow": "onboarding",
        "likelihood": "low",
        "impact": "minor UI confusion",
        "workaround": "manager clarifies verbally",
        "owner": "core maintainer",
        "blocking": False,
        "disposition": "Accepted for F1",
    }


def test_p6_readiness_rejects_blocking_limitations_and_non_utc_decision() -> None:
    """Blocking limitations and local timestamps keep the gate open."""
    validator = load_script("validate_p6_readiness")
    document = valid_p6_readiness()
    document["known_limitations"] = [{**valid_limitation(), "blocking": True}]
    document["decision"]["decided_at"] = "2026-09-12T04:00:00-07:00"
    errors = validator.validate_readiness(document)
    assert "known_limitations[0] remains release blocking" in errors
    assert (
        "decision.decided_at must be an ISO 8601 UTC timestamp (Z or +00:00 only)"
        in errors
    )


def test_p6_readiness_accepts_a_well_formed_non_blocking_limitation() -> None:
    """A fully completed, already-resolved limitation does not block P6."""
    validator = load_script("validate_p6_readiness")
    document = valid_p6_readiness()
    document["known_limitations"] = [valid_limitation()]
    assert validator.validate_readiness(document) == []


def test_p6_readiness_rejects_incomplete_limitation_fields() -> None:
    """Every required limitation field is checked, not just id/summary/disposition."""
    validator = load_script("validate_p6_readiness")
    validator_module = validator
    limitation = {**valid_limitation(), "affected_role": "pending", "owner": ""}
    errors = validator_module.validate_limitations([limitation])
    assert "known_limitations[0].affected_role must be completed text" in errors
    assert "known_limitations[0].owner must be completed text" in errors


def test_completed_text_accepts_legitimate_prose_containing_pending() -> None:
    """A substring match would wrongly reject prose that contains 'pending'."""
    validator = load_script("validate_p6_readiness")
    assert validator.completed_text("no longer depending on the LLM provider") is True


@pytest.mark.parametrize("junk", ["TBD", "N/A", "TODO", "x", "-", "?", "  fixme  "])
def test_completed_text_rejects_obvious_non_completions(junk: str) -> None:
    """Short junk tokens are not template placeholders but are not real data."""
    validator = load_script("validate_p6_readiness")
    assert validator.completed_text(junk) is False


def test_decided_at_accepts_fractional_seconds_regardless_of_digit_count() -> None:
    """A 2-digit fraction was rejected on 3.10 and accepted on 3.11+.

    The validator now defines its own grammar (padding the fraction to six
    digits before the one canonical form is parsed), so this is accepted
    deterministically instead of depending on which CPython runs it.
    """
    validator = load_script("validate_p6_readiness")
    document = valid_p6_readiness()
    document["decision"]["decided_at"] = "2026-09-12T04:00:00.12Z"
    assert validator.validate_readiness(document) == []


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-09-12T04:00:00+0000",  # offset missing the required colon
        "20260912T040000Z",  # basic format, no date/time separators
    ],
)
def test_decided_at_rejects_non_canonical_variants(timestamp: str) -> None:
    """Variants outside the validator's own grammar are rejected consistently.

    `datetime.fromisoformat` accepts both of these on Python 3.11+ (and
    rejects them on 3.10); the validator's own grammar rejects both on every
    supported interpreter instead of inheriting that version-dependent
    leniency.
    """
    validator = load_script("validate_p6_readiness")
    document = valid_p6_readiness()
    document["decision"]["decided_at"] = timestamp
    errors = validator.validate_readiness(document)
    assert any(error.startswith("decision.decided_at") for error in errors)


def test_decided_at_rejects_offset_unknown() -> None:
    """RFC 3339 '-00:00' means offset unknown, not attributable UTC."""
    validator = load_script("validate_p6_readiness")
    document = valid_p6_readiness()
    document["decision"]["decided_at"] = "2026-09-12T04:00:00-00:00"
    errors = validator.validate_readiness(document)
    assert any(error.startswith("decision.decided_at") for error in errors)


def test_decided_at_accepts_lowercase_z() -> None:
    """RFC 3339 permits a lowercase 'z' designator."""
    validator = load_script("validate_p6_readiness")
    document = valid_p6_readiness()
    document["decision"]["decided_at"] = "2026-09-12t04:00:00z"
    assert validator.validate_readiness(document) == []


def test_gate_value_normalizes_like_every_other_text_field() -> None:
    """Gate values should not require exact-match 'pass' unlike other fields."""
    validator = load_script("validate_p6_readiness")
    document = valid_p6_readiness()
    document["gates"]["P6.1"] = " Pass "
    assert validator.validate_readiness(document) == []


def test_private_reference_rejects_a_public_url() -> None:
    """A public URL is not a private evidence reference."""
    validator = load_script("validate_p6_readiness")
    document = valid_p6_readiness()
    document["release"]["deployment_reference"] = "https://example.com/release"
    errors = validator.validate_readiness(document)
    assert (
        "release.deployment_reference must use the private:<opaque-reference> format"
        in errors
    )


def test_main_reports_exit_code_two_for_non_utf8_input(tmp_path: Path) -> None:
    """A non-UTF-8 record fails the documented I/O contract, not a traceback."""
    validator = load_script("validate_p6_readiness")
    record = tmp_path / "bad_encoding.json"
    record.write_bytes(b"\xff\xfe{}")
    argv = ["validate_p6_readiness.py", str(record)]
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("sys.argv", argv)
        assert validator.main() == 2


def valid_topology() -> dict[str, Any]:
    """Return the minimum valid rendered production topology."""
    return {
        "services": {
            "app": {
                "networks": {"fragrance_rater-network": None},
                "environment": {
                    "AUTHENTIK_REQUIRED": "true",
                    "DATABASE_URL": "postgresql+asyncpg://app:secret@db/app",
                },
            },
            "frontend": {
                "environment": {"VITE_API_URL": "/api"},
                "networks": {
                    "fragrance_rater-network": None,
                    "authenticated-edge": None,
                },
                "labels": {
                    "traefik.enable": "true",
                    "traefik.http.routers.fragrance-rater.middlewares": (
                        "security-headers@file, authentik@file"
                    ),
                },
            },
            "db": {"networks": {"fragrance_rater-network": None}},
        },
        "networks": {"authenticated-edge": {"external": True}},
    }


def test_production_topology_rejects_direct_backend_port() -> None:
    """A host-published API is an Authentik bypass even when headers are checked."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"]["app"]["ports"] = [{"published": "8000", "target": 8000}]
    assert validator.validate_topology(config) == ["service app publishes a host port"]


@pytest.mark.parametrize(
    ("service", "network_mode"),
    [
        ("app", "host"),
        ("app", "service:frontend"),
        ("app", "container:proxy"),
        ("db", "host"),
        ("db", "service:app"),
        ("db", "container:database"),
    ],
)
def test_production_topology_rejects_private_network_modes(
    service: str, network_mode: str
) -> None:
    """Private services cannot bypass declared network isolation."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"][service]["network_mode"] = network_mode
    assert validator.validate_topology(config) == [
        f"service {service} must not set network_mode={network_mode}"
    ]


def test_production_topology_rejects_unrelated_middleware_chain() -> None:
    """A router must name the expected Authentik middleware token."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"]["frontend"]["labels"][
        "traefik.http.routers.fragrance-rater.middlewares"
    ] = "security-headers@file"
    assert validator.validate_topology(config) == [
        "Traefik router must declare the Authentik middleware"
    ]


def test_production_topology_keeps_private_services_off_edge_network() -> None:
    """The API and database cannot join the externally reachable edge."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"]["db"]["networks"]["authenticated-edge"] = None
    assert validator.validate_topology(config) == [
        "service db must not join the authenticated-edge network"
    ]
