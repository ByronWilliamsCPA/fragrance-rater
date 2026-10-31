"""Tests for release-evidence validators used by P1."""

from __future__ import annotations

import importlib.util
import json
import sys
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


def valid_entry(**overrides: object) -> dict[str, Any]:
    """Return a minimum valid manifest entry, with fields overridden."""
    entry: dict[str, Any] = {
        "membership_key": "m1",
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
    entry.update(overrides)
    return entry


def test_manifest_accepts_a_valid_gtin() -> None:
    """A real, check-digit-valid GTIN (Chanel N5 Parfum's, per its Parfumo
    page) passes; gtin is otherwise optional."""
    validator = load_script("validate_calibration_manifest")
    document = {
        "program_name": "Baseline",
        "program_version": "v1",
        "entries": [valid_entry(gtin="3508440005953")],
    }
    assert validator.validate_manifest(document) == []


def test_manifest_omitted_gtin_is_not_an_error() -> None:
    validator = load_script("validate_calibration_manifest")
    document = {
        "program_name": "Baseline",
        "program_version": "v1",
        "entries": [valid_entry()],
    }
    assert validator.validate_manifest(document) == []


def test_manifest_rejects_a_gtin_with_a_bad_check_digit() -> None:
    """A GTIN that fails its GS1 check digit is far more likely a
    transcription typo than a real identifier, so it is release-blocking
    rather than silently accepted as free text."""
    validator = load_script("validate_calibration_manifest")
    document = {
        "program_name": "Baseline",
        "program_version": "v1",
        "entries": [valid_entry(gtin="3508440005950")],
    }
    errors = validator.validate_manifest(document)
    assert any("gtin must be a valid GTIN" in error for error in errors)


def test_manifest_rejects_a_gtin_authored_as_a_json_number() -> None:
    """A JSON number has no leading-zero literal, so an author who wrote
    an unquoted 36000291452 instead of "036000291452" has already lost a
    digit before this script runs; str(gtin) coercion would accept the
    mistake (or reject it with a misleading "invalid GTIN" instead of
    naming the real cause). The manifest's gtin field must be authored
    as a JSON string, matching MembershipInput's live-path contract."""
    validator = load_script("validate_calibration_manifest")
    document = {
        "program_name": "Baseline",
        "program_version": "v1",
        "entries": [valid_entry(gtin=36000291452)],
    }
    errors = validator.validate_manifest(document)
    assert any("must be a JSON string" in error for error in errors)


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


def _document_with_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Wrap a single manifest entry in a minimal valid document envelope."""
    return {
        "program_name": "Baseline",
        "program_version": "v1",
        "entries": [entry],
    }


class TestSourceEvidence:
    """P1.1 evidence contract (ADR-012's SourceSnapshot amendment):
    source_url and source_reference each stand alone as evidence, so at
    least one must be present and a non-blank string. A key that is
    present but the wrong type (an int, a list, a dict, an explicit JSON
    null) is a distinct authoring mistake from omitting the key entirely
    and must be reported as its own error, not silently treated the same
    as "absent". Also covers the urlparse crash a malformed source_url
    (e.g. an unterminated IPv6 host) would otherwise cause, which must be
    turned into a validation error rather than losing every error already
    accumulated for the run.
    """

    def test_source_url_only_is_sufficient(self) -> None:
        validator = load_script("validate_calibration_manifest")
        entry = valid_entry(source_url="https://example.test/scent")
        assert validator.validate_manifest(_document_with_entry(entry)) == []

    def test_source_reference_only_is_sufficient(self) -> None:
        validator = load_script("validate_calibration_manifest")
        entry = valid_entry(source_reference="Email from brand rep, 2026-09-20")
        del entry["source_url"]
        assert validator.validate_manifest(_document_with_entry(entry)) == []

    def test_both_source_url_and_reference_present_is_accepted(self) -> None:
        validator = load_script("validate_calibration_manifest")
        entry = valid_entry(
            source_url="https://example.test/scent",
            source_reference="Email from brand rep, 2026-09-20",
        )
        assert validator.validate_manifest(_document_with_entry(entry)) == []

    def test_neither_source_field_is_rejected(self) -> None:
        validator = load_script("validate_calibration_manifest")
        entry = valid_entry()
        del entry["source_url"]
        errors = validator.validate_manifest(_document_with_entry(entry))
        assert any(
            "must have a non-empty source_url or source_reference" in error
            for error in errors
        )

    @pytest.mark.parametrize("bad_value", [123, ["a"], {"a": "b"}, None])
    def test_source_url_wrong_type_is_rejected(self, bad_value: object) -> None:
        validator = load_script("validate_calibration_manifest")
        entry = valid_entry(source_url=bad_value)
        errors = validator.validate_manifest(_document_with_entry(entry))
        assert any("source_url must be a non-empty string" in error for error in errors)

    def test_source_url_blank_string_is_rejected(self) -> None:
        validator = load_script("validate_calibration_manifest")
        entry = valid_entry(source_url="   ")
        errors = validator.validate_manifest(_document_with_entry(entry))
        assert any("source_url must be a non-empty string" in error for error in errors)

    @pytest.mark.parametrize("bad_value", [123, ["a"], {"a": "b"}, None])
    def test_source_reference_wrong_type_is_rejected(self, bad_value: object) -> None:
        validator = load_script("validate_calibration_manifest")
        entry = valid_entry(source_reference=bad_value)
        errors = validator.validate_manifest(_document_with_entry(entry))
        assert any(
            "source_reference must be a non-empty string" in error for error in errors
        )

    def test_source_reference_blank_string_is_rejected(self) -> None:
        validator = load_script("validate_calibration_manifest")
        entry = valid_entry(source_reference="   ")
        del entry["source_url"]
        errors = validator.validate_manifest(_document_with_entry(entry))
        assert any(
            "source_reference must be a non-empty string" in error for error in errors
        )

    def test_malformed_source_url_is_reported_not_a_crash(self) -> None:
        """An unterminated IPv6 host raises ValueError from urlparse
        itself; the validator must catch it and keep every error already
        accumulated for this entry rather than losing them to an
        unhandled exception."""
        validator = load_script("validate_calibration_manifest")
        entry = valid_entry(source_url="https://[::1", physical_sample_confirmed=False)
        errors = validator.validate_manifest(_document_with_entry(entry))
        assert any(
            "source_url must be an absolute HTTPS URL" in error for error in errors
        )
        # The malformed URL must not have short-circuited validation of
        # the rest of the entry (physical_sample_confirmed is also wrong).
        assert any("physical_sample_confirmed" in error for error in errors)


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
        "2026-09-12 04:00:00Z",  # space date-time separator, not RFC 3339
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
                    "ENVIRONMENT": "production",
                    "TRUSTED_HOSTS": "fragrance.example.com,localhost,127.0.0.1",
                    "FORWARDED_ALLOW_IPS": "172.25.0.0/16,172.30.0.0/24",
                    "DATABASE_URL": "postgresql+asyncpg://app:secret@db/app",
                    "CALIBRATION_ADMIN_USERNAMES": '["manager"]',
                    "FRAGRANCE_RATER_API_KEY": "test-household-api-key-value",
                    "OPENROUTER_API_KEY": "test-openrouter-api-key-value",
                },
            },
            "frontend": {
                "environment": {
                    "VITE_API_URL": "/api",
                    "FRAGRANCE_TRAEFIK_CIDR": "172.30.0.0/24",
                },
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
        "Traefik router must declare the Authentik middleware 'authentik@file'"
    ]


def test_production_topology_keeps_private_services_off_edge_network() -> None:
    """The API and database cannot join the externally reachable edge."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"]["db"]["networks"]["authenticated-edge"] = None
    assert validator.validate_topology(config) == [
        "service db must not join the authenticated-edge network"
    ]


def _too_broad(cidr: str, prefix: int) -> str:
    return (
        f"FRAGRANCE_TRAEFIK_CIDR {cidr!r} is broader than /{prefix}; "
        "trust only the dedicated edge network"
    )


@pytest.mark.parametrize(
    ("cidr", "message"),
    [
        (None, "frontend must set FRAGRANCE_TRAEFIK_CIDR to the edge network subnet"),
        ("", "frontend must set FRAGRANCE_TRAEFIK_CIDR to the edge network subnet"),
        ("edge-net", "FRAGRANCE_TRAEFIK_CIDR 'edge-net' is not a valid CIDR"),
        (
            "0.0.0.0/0",
            _too_broad("0.0.0.0/0", 16),
        ),
        (
            "172.16.0.0/12",
            _too_broad("172.16.0.0/12", 16),
        ),
        (
            "fd00::/8",
            _too_broad("fd00::/8", 48),
        ),
    ],
)
def test_production_topology_requires_a_narrow_edge_cidr(
    cidr: str | None, message: str
) -> None:
    """nginx trusts identity headers only from this subnet (R3, S-01)."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    environment = config["services"]["frontend"]["environment"]
    if cidr is None:
        del environment["FRAGRANCE_TRAEFIK_CIDR"]
    else:
        environment["FRAGRANCE_TRAEFIK_CIDR"] = cidr
    assert validator.validate_topology(config) == [message]


@pytest.mark.parametrize("cidr", ["172.30.0.0/24", "10.20.0.0/16", "fd12:3456::/64"])
def test_production_topology_accepts_a_dedicated_edge_cidr(cidr: str) -> None:
    """Typical Docker bridge subnets pass."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"]["frontend"]["environment"]["FRAGRANCE_TRAEFIK_CIDR"] = cidr
    assert validator.validate_topology(config) == []


def _mismatch(live: str) -> str:
    return (
        "FRAGRANCE_TRAEFIK_CIDR '172.30.0.0/24' does not match the edge "
        f"network subnet {live!r}"
    )


@pytest.mark.parametrize("live", ["172.30.0.0/24", " 172.30.0.0/24\n", "172.30.0.5/24"])
def test_production_topology_accepts_the_live_edge_subnet(live: str) -> None:
    """The CIDR matches the subnet Docker reports for the edge network."""
    validator = load_script("validate_production_topology")
    assert validator.validate_topology(valid_topology(), edge_subnet=live) == []


@pytest.mark.parametrize(
    ("live", "message"),
    [
        ("172.30.0.0/16", _mismatch("172.30.0.0/16")),
        ("172.31.0.0/24", _mismatch("172.31.0.0/24")),
        ("", "edge network subnet '' is not a valid CIDR"),
    ],
)
def test_production_topology_rejects_a_cidr_that_is_not_the_live_subnet(
    live: str, message: str
) -> None:
    """A stale or mistyped CIDR can exclude Traefik or trust other peers."""
    validator = load_script("validate_production_topology")
    assert validator.validate_topology(valid_topology(), edge_subnet=live) == [message]


def test_production_topology_cli_requires_the_live_edge_subnet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The deployment check cannot run without the inspected subnet."""
    validator = load_script("validate_production_topology")
    rendered = tmp_path / "compose.json"
    rendered.write_text(json.dumps(valid_topology()), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["validate", str(rendered)])
    assert validator.main() == 2
    assert "EDGE_SUBNET" in capsys.readouterr().err

    monkeypatch.setattr(sys, "argv", ["validate", str(rendered), "172.31.0.0/24"])
    assert validator.main() == 1
    assert "does not match" in capsys.readouterr().err

    monkeypatch.setattr(sys, "argv", ["validate", str(rendered), "172.30.0.0/24"])
    assert validator.main() == 0


@pytest.mark.parametrize("hosts", [None, "", "*", "fragrance.example.com,*"])
def test_production_topology_requires_explicit_trusted_hosts(
    hosts: str | None,
) -> None:
    """The API must validate the Host header in production (R3, B-27)."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    environment = config["services"]["app"]["environment"]
    if hosts is None:
        del environment["TRUSTED_HOSTS"]
    else:
        environment["TRUSTED_HOSTS"] = hosts
    assert validator.validate_topology(config) == [
        "app must set TRUSTED_HOSTS to explicit host names"
    ]


def test_production_topology_requires_production_environment() -> None:
    """ENVIRONMENT=production is what turns off docs and dev CORS (R3, S-18)."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"]["app"]["environment"]["ENVIRONMENT"] = "development"
    assert validator.validate_topology(config) == [
        "app must set ENVIRONMENT=production"
    ]


@pytest.mark.parametrize("allowed", [None, "", "*", "172.25.0.0/16,*"])
def test_production_topology_requires_explicit_forwarded_allow_ips(
    allowed: str | None,
) -> None:
    """uvicorn must not trust X-Forwarded-For from arbitrary peers (R3, S-02)."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    environment = config["services"]["app"]["environment"]
    if allowed is None:
        del environment["FORWARDED_ALLOW_IPS"]
    else:
        environment["FORWARDED_ALLOW_IPS"] = allowed
    assert validator.validate_topology(config) == [
        "app must set FORWARDED_ALLOW_IPS to the proxy subnets"
    ]


# --- S-04 and S-08: the app container's runtime requirements -----------------


def _app_environment(config: dict[str, Any]) -> dict[str, Any]:
    return config["services"]["app"]["environment"]


def test_production_topology_accepts_a_configured_middleware_name() -> None:
    """The expected middleware is an argument, not a hard-coded constant (S-08)."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    labels = config["services"]["frontend"]["labels"]
    labels["traefik.http.routers.fragrance-rater.middlewares"] = "sso-forward@docker"

    assert (
        validator.validate_topology(config, authentik_middleware="sso-forward@docker")
        == []
    )
    assert validator.validate_topology(config) == [
        "Traefik router must declare the Authentik middleware 'authentik@file'"
    ]


@pytest.mark.parametrize("replicas", [1, "1", None])
def test_production_topology_accepts_a_single_app_replica(replicas: object) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    if replicas is not None:
        config["services"]["app"]["deploy"] = {"replicas": replicas}

    assert validator.validate_topology(config) == []


@pytest.mark.parametrize("replicas", [2, "3", 0])
def test_production_topology_rejects_more_than_one_app_replica(
    replicas: object,
) -> None:
    """The rate limiter is process-local: replicas multiply the effective limit."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"]["app"]["deploy"] = {"replicas": replicas}

    errors = validator.validate_topology(config)

    assert len(errors) == 1
    assert "single replica" in errors[0]


@pytest.mark.parametrize("value", ['["manager"]', "manager", "manager, second"])
def test_production_topology_accepts_a_named_manager_allow_list(value: str) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    _app_environment(config)["CALIBRATION_ADMIN_USERNAMES"] = value

    assert validator.validate_topology(config) == []


@pytest.mark.parametrize(
    ("value", "fragment"),
    [
        (None, "must be a JSON array or comma list"),
        ("[]", "at least one manager"),
        ("", "at least one manager"),
        ('["manager", ""]', "at least one manager"),
        ('["*"]', "wildcard"),
        ("manager,*", "wildcard"),
        ("[not json", "must be a JSON array or comma list"),
        ('["manager", 42]', "must be a JSON array or comma list"),
    ],
)
def test_production_topology_rejects_a_bad_manager_allow_list(
    value: str | None, fragment: str
) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    if value is None:
        del _app_environment(config)["CALIBRATION_ADMIN_USERNAMES"]
    else:
        _app_environment(config)["CALIBRATION_ADMIN_USERNAMES"] = value

    errors = validator.validate_topology(config)

    assert len(errors) == 1
    assert fragment in errors[0]


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        '["https://fragrance.example.com"]',
        "https://a.example,https://b.example",
    ],
)
def test_production_topology_accepts_unset_or_https_cors(value: str | None) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    if value is not None:
        _app_environment(config)["CORS_ALLOWED_ORIGINS"] = value

    assert validator.validate_topology(config) == []


@pytest.mark.parametrize(
    ("value", "fragment"),
    [
        ('["*"]', "wildcard"),
        ("*", "wildcard"),
        ("http://fragrance.example.com", "https origin"),
        ('["https://ok.example", "http://localhost:3000"]', "https origin"),
    ],
)
def test_production_topology_rejects_open_or_insecure_cors(
    value: str, fragment: str
) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    _app_environment(config)["CORS_ALLOWED_ORIGINS"] = value

    errors = validator.validate_topology(config)

    assert errors
    assert all(fragment in error for error in errors)


@pytest.mark.parametrize("name", ["FRAGRANCE_RATER_API_KEY", "OPENROUTER_API_KEY"])
def test_production_topology_requires_each_billed_endpoint_secret(name: str) -> None:
    """Neither secret reaches the container unless the override passes it (S-04)."""
    validator = load_script("validate_production_topology")
    missing = valid_topology()
    del _app_environment(missing)[name]
    blank = valid_topology()
    _app_environment(blank)[name] = "   "

    assert validator.validate_topology(missing) == [f"app must set {name}"]
    assert validator.validate_topology(blank) == [f"app must set {name}"]


@pytest.mark.parametrize(
    "value",
    [
        "your-openrouter-api-key-here",
        "changeme",
        "CHANGE_ME",
        "<paste key>",
        "${OPENROUTER_API_KEY}",
        "sk-or-v1-xxxxxxxxxxxx",
        "example-key",
        "placeholder",
    ],
)
def test_production_topology_rejects_a_placeholder_secret(value: str) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    _app_environment(config)["OPENROUTER_API_KEY"] = value

    assert validator.validate_topology(config) == [
        "app OPENROUTER_API_KEY is a placeholder, not a secret"
    ]


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on", "t", "y"])
def test_production_topology_rejects_test_mode(value: str) -> None:
    """TEST_MODE swaps real model output for a fixture (S-27)."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    _app_environment(config)["TEST_MODE"] = value

    assert validator.validate_topology(config) == [
        "app must not set TEST_MODE in production"
    ]


@pytest.mark.parametrize("value", ["false", "0", ""])
def test_production_topology_accepts_test_mode_off(value: str) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    _app_environment(config)["TEST_MODE"] = value

    assert validator.validate_topology(config) == []


def _run_main(validator: Any, monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr("sys.argv", ["validate_production_topology.py", *argv])
    return validator.main()


def test_main_takes_the_middleware_from_the_flag_then_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    labels = config["services"]["frontend"]["labels"]
    labels["traefik.http.routers.fragrance-rater.middlewares"] = "sso-forward@docker"
    path = tmp_path / "render.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.delenv("AUTHENTIK_MIDDLEWARE", raising=False)

    assert _run_main(validator, monkeypatch, str(path), "172.30.0.0/24") == 1
    assert (
        _run_main(
            validator,
            monkeypatch,
            str(path),
            "172.30.0.0/24",
            "--authentik-middleware",
            "sso-forward@docker",
        )
        == 0
    )
    monkeypatch.setenv("AUTHENTIK_MIDDLEWARE", "sso-forward@docker")
    assert _run_main(validator, monkeypatch, str(path), "172.30.0.0/24") == 0


def test_main_still_requires_both_positional_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validator = load_script("validate_production_topology")

    assert _run_main(validator, monkeypatch, "only-one.json") == 2
