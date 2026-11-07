"""Tests for release-evidence validators used by P1."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).parents[2]

# The verifier block every complete manifest carries (the template ships both as null).
VERIFIED: dict[str, str] = {
    "verified_by": "A. Verifier",
    "verified_at": "2026-11-08T14:30:00Z",
}


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
        **VERIFIED,
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
        **VERIFIED,
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
        **VERIFIED,
        "entries": [valid_entry(gtin="3508440005953")],
    }
    assert validator.validate_manifest(document) == []


def test_manifest_omitted_gtin_is_not_an_error() -> None:
    validator = load_script("validate_calibration_manifest")
    document = {
        "program_name": "Baseline",
        "program_version": "v1",
        **VERIFIED,
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
        **VERIFIED,
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
        **VERIFIED,
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
        **VERIFIED,
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
        **VERIFIED,
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
        entry = valid_entry(
            source_reference="B. Williams | 2026-09-20 | decant label check"
        )
        del entry["source_url"]
        assert validator.validate_manifest(_document_with_entry(entry)) == []

    def test_both_source_url_and_reference_present_is_accepted(self) -> None:
        validator = load_script("validate_calibration_manifest")
        entry = valid_entry(
            source_url="https://example.test/scent",
            source_reference="B. Williams | 2026-09-20 | decant label check",
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

    @pytest.mark.parametrize(
        "bad_value",
        [
            "Email from brand rep, 2026-09-20",
            "who | 2026-09-20",
            "who | | scope",
            "who | 20-09-2026 | scope",
            "who | 2026-13-40 | scope",
            "who | 20260920 | scope",
            "who | 2026-W38-7 | scope",
            "a | 2026-09-20 | b | c",
        ],
    )
    def test_source_reference_must_follow_the_minimal_format(
        self, bad_value: str
    ) -> None:
        """Reference is who | ISO date | evidence or scope."""
        validator = load_script("validate_calibration_manifest")
        entry = valid_entry(source_reference=bad_value)
        del entry["source_url"]

        errors = validator.validate_manifest(_document_with_entry(entry))

        assert any("source_reference" in error for error in errors)

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


class TestManifestVerification:
    """P1.1: a manifest records who verified it and when, as in the template."""

    def test_a_complete_verifier_block_passes(self) -> None:
        validator = load_script("validate_calibration_manifest")
        assert validator.validate_manifest(_document_with_entry(valid_entry())) == []

    @pytest.mark.parametrize("value", [None, "", "   ", 7, ["A. Verifier"]])
    def test_verified_by_must_be_a_name(self, value: object) -> None:
        validator = load_script("validate_calibration_manifest")
        document = {**_document_with_entry(valid_entry()), "verified_by": value}
        errors = validator.validate_manifest(document)
        assert any("verified_by" in error for error in errors)

    def test_the_blank_template_fields_fail(self) -> None:
        validator = load_script("validate_calibration_manifest")
        template = json.loads(
            (ROOT / "data/calibration/baseline-manifest.template.json").read_text(
                encoding="utf-8"
            )
        )
        document = {**_document_with_entry(valid_entry()), **template}
        document["entries"] = [valid_entry()]
        errors = validator.validate_manifest(document)
        assert any("verified_by" in error for error in errors)
        assert any("verified_at" in error for error in errors)

    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "2026-11-08",
            "2026-11-08 14:30:00",
            "2026-11-08T14:30:00+00:00",
            "2026-11-08T14:30:00",
            "2026-13-08T14:30:00Z",
            "2026-11-08T25:30:00Z",
            20261108,
        ],
    )
    def test_verified_at_must_be_a_real_utc_timestamp(self, value: object) -> None:
        validator = load_script("validate_calibration_manifest")
        document = {**_document_with_entry(valid_entry()), "verified_at": value}
        errors = validator.validate_manifest(document)
        assert any("verified_at" in error for error in errors)

    def test_fractional_seconds_are_accepted(self) -> None:
        validator = load_script("validate_calibration_manifest")
        document = {
            **_document_with_entry(valid_entry()),
            "verified_at": "2026-11-08T14:30:00.250Z",
        }
        assert validator.validate_manifest(document) == []


class TestLabelCheck:
    """The owner's 2026-11-01 decant standard: two people check the label."""

    def test_absent_is_allowed_by_default(self) -> None:
        validator = load_script("validate_calibration_manifest")
        assert validator.validate_manifest(_document_with_entry(valid_entry())) == []

    def test_absent_fails_when_required(self) -> None:
        validator = load_script("validate_calibration_manifest")
        errors = validator.validate_manifest(
            _document_with_entry(valid_entry()), require_label_check=True
        )
        assert errors == ["entries[0].label_checked_by is required (two people)"]

    def test_two_different_people_pass(self) -> None:
        validator = load_script("validate_calibration_manifest")
        entry = valid_entry(label_checked_by=["A. Verifier", "B. Second"])
        document = _document_with_entry(entry)
        assert validator.validate_manifest(document, require_label_check=True) == []

    @pytest.mark.parametrize(
        "names",
        [
            ["A. Verifier"],
            ["A. Verifier", "a. verifier"],
            ["A. Verifier", "  A. VERIFIER  "],
        ],
    )
    def test_one_person_counted_twice_fails(self, names: list[str]) -> None:
        validator = load_script("validate_calibration_manifest")
        document = _document_with_entry(valid_entry(label_checked_by=names))
        errors = validator.validate_manifest(document)
        assert errors == ["entries[0].label_checked_by needs 2 different people"]

    @pytest.mark.parametrize(
        "names", [[], "A. Verifier", None, ["A. Verifier", ""], ["A", 2], {"a": "b"}]
    )
    def test_malformed_values_fail_without_crashing(self, names: object) -> None:
        validator = load_script("validate_calibration_manifest")
        document = _document_with_entry(valid_entry(label_checked_by=names))
        errors = validator.validate_manifest(document)
        assert errors == [
            "entries[0].label_checked_by must be a list of non-empty names"
        ]


def _shape_document(baseline: int, repeats: int, holdout: int) -> dict[str, Any]:
    """Build a manifest with the given number of memberships per role."""
    entries: list[dict[str, Any]] = [
        valid_entry(
            membership_key=f"b{index}",
            fragrance_id=f"fb{index}",
            version_key=f"v-b{index}",
        )
        for index in range(baseline)
    ]
    entries.extend(
        valid_entry(
            membership_key=f"r{index}",
            fragrance_id="fb0",
            version_key="v-b0",
            role="HIDDEN_REPEAT",
            repeat_of_membership_key="b0",
        )
        for index in range(repeats)
    )
    entries.extend(
        valid_entry(
            membership_key=f"h{index}",
            fragrance_id=f"fh{index}",
            version_key=f"v-h{index}",
            role="HOLDOUT",
        )
        for index in range(holdout)
    )
    return {**_document_with_entry(valid_entry()), "entries": entries}


class TestExpectedShape:
    """The intended program is 33 baseline, 6 hidden repeat and 10 holdout."""

    def test_the_f1_shape_is_accepted(self) -> None:
        validator = load_script("validate_calibration_manifest")
        document = _shape_document(33, 6, 10)
        expected = validator.parse_shape("baseline=33,hidden_repeat=6,holdout=10")
        assert validator.validate_manifest(document) == []
        assert validator.validate_shape(document, expected) == []
        assert len(document["entries"]) == 49

    def test_a_missing_membership_is_named(self) -> None:
        validator = load_script("validate_calibration_manifest")
        document = _shape_document(33, 6, 9)
        errors = validator.validate_shape(document, {"holdout": 10})
        assert errors == ["expected 10 holdout membership(s) (HOLDOUT), found 9"]

    def test_each_wrong_role_is_reported(self) -> None:
        validator = load_script("validate_calibration_manifest")
        document = _shape_document(2, 1, 0)
        errors = validator.validate_shape(
            document, {"baseline": 3, "hidden_repeat": 1, "holdout": 1}
        )
        assert len(errors) == 2
        assert any("baseline" in error for error in errors)
        assert any("holdout" in error for error in errors)

    def test_an_extra_membership_of_another_role_fails_the_total(self) -> None:
        validator = load_script("validate_calibration_manifest")
        document = _shape_document(33, 6, 10)
        document["entries"].append(
            valid_entry(
                membership_key="a0",
                fragrance_id="fa0",
                version_key="v-a0",
                role="ACTIVE_LEARNING",
            )
        )
        expected = validator.parse_shape(
            "baseline=33,hidden_repeat=6,holdout=10,total=49"
        )
        assert validator.validate_shape(document, expected) == [
            "expected 49 membership(s) in total, found 50"
        ]

    def test_the_total_matches_when_every_role_is_counted(self) -> None:
        validator = load_script("validate_calibration_manifest")
        expected = validator.parse_shape("total=49")
        assert validator.validate_shape(_shape_document(33, 6, 10), expected) == []

    def test_a_shape_without_a_total_ignores_other_roles(self) -> None:
        validator = load_script("validate_calibration_manifest")
        document = _shape_document(1, 0, 0)
        document["entries"].append(
            valid_entry(
                membership_key="a0",
                fragrance_id="fa0",
                version_key="v-a0",
                role="ACTIVE_LEARNING",
            )
        )
        assert validator.validate_shape(document, {"baseline": 1}) == []

    def test_an_unusable_document_adds_no_shape_noise(self) -> None:
        validator = load_script("validate_calibration_manifest")
        assert validator.validate_shape([], {"baseline": 1}) == []
        assert validator.validate_shape({"entries": "x"}, {"baseline": 1}) == []

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "baseline",
            "baseline=",
            "baseline=x",
            "baseline=-1",
            "other=3",
            "baseline=1,baseline=2",
            "baseline=1,,holdout=2",
            "total=",
            "total=1,total=2",
        ],
    )
    def test_parse_shape_rejects_malformed_text(self, text: str) -> None:
        validator = load_script("validate_calibration_manifest")
        with pytest.raises(argparse.ArgumentTypeError):
            validator.parse_shape(text)


class TestManifestCommandLine:
    """The command line wires the checks together and keeps its exit codes."""

    def _write(self, tmp_path: Path, document: object) -> str:
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return str(path)

    def test_valid_manifest_exits_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        validator = load_script("validate_calibration_manifest")
        path = self._write(tmp_path, _shape_document(3, 1, 1))
        assert validator.main([path]) == 0
        assert "5 entries" in capsys.readouterr().out

    def test_expect_shape_failure_exits_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        validator = load_script("validate_calibration_manifest")
        path = self._write(tmp_path, _shape_document(3, 1, 1))
        assert validator.main([path, "--expect-shape", "holdout=2"]) == 1
        assert "expected 2 holdout" in capsys.readouterr().err

    def test_shape_and_label_check_together_exit_zero(self, tmp_path: Path) -> None:
        validator = load_script("validate_calibration_manifest")
        document = _shape_document(3, 1, 1)
        for entry in document["entries"]:
            entry["label_checked_by"] = ["A. Verifier", "B. Second"]
        path = self._write(tmp_path, document)
        argv = [
            path,
            "--expect-shape",
            "baseline=3,hidden_repeat=1,holdout=1,total=5",
            "--require-label-check",
        ]
        assert validator.main(argv) == 0

    def test_require_label_check_failure_exits_one(self, tmp_path: Path) -> None:
        validator = load_script("validate_calibration_manifest")
        path = self._write(tmp_path, _shape_document(1, 0, 0))
        assert validator.main([path, "--require-label-check"]) == 1

    def test_a_manifest_with_verifier_errors_exits_one(self, tmp_path: Path) -> None:
        validator = load_script("validate_calibration_manifest")
        document = {**_shape_document(1, 0, 0), "verified_by": None}
        assert validator.main([self._write(tmp_path, document)]) == 1

    def test_unreadable_files_exit_two(self, tmp_path: Path) -> None:
        validator = load_script("validate_calibration_manifest")
        assert validator.main([str(tmp_path / "absent.json")]) == 2
        broken = tmp_path / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        assert validator.main([str(broken)]) == 2
        binary = tmp_path / "binary.json"
        binary.write_bytes(b"\xff\xfe\x00")
        assert validator.main([str(binary)]) == 2

    def test_a_bad_shape_argument_exits_two(self, tmp_path: Path) -> None:
        validator = load_script("validate_calibration_manifest")
        path = self._write(tmp_path, _shape_document(1, 0, 0))
        with pytest.raises(SystemExit) as raised:
            validator.main([path, "--expect-shape", "nonsense"])
        assert raised.value.code == 2


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
        "r7b_build": {
            "commit": "a" * 40,
            "app_image_digest": f"sha256:{'b' * 64}",
            "frontend_image_digest": f"sha256:{'c' * 64}",
        },
        "gates": {f"P6.{index}": "pass" for index in range(1, 7)},
        "artifacts": {
            "p1_gate": "private:p1",
            "device_matrix": "private:devices",
            "synthetic_rehearsal": "private:rehearsal",
            "redacted_export_manifest": "private:export",
            "redacted_r7b_export": "private:r7b-export",
            "quality_report": "private:quality",
            "operations_drill": "private:operations",
            "signed_decision": "private:decision",
        },
        "known_limitations": [],
        "known_limitations_review": "Reviewed on 2026-09-12; none identified",
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


class TestR7bBuildBinding:
    """P6.3 evidence must be about the build the release candidate names."""

    def test_the_template_fails_on_every_new_field(self) -> None:
        validator = load_script("validate_p6_readiness")
        template = json.loads(
            (ROOT / "data" / "pilot" / "p6-readiness.template.json").read_text(
                encoding="utf-8"
            )
        )
        errors = validator.validate_readiness(template)
        assert "r7b_build.commit must be a 40-character lowercase Git commit" in errors
        assert (
            "r7b_build.app_image_digest must be an immutable SHA-256 digest" in errors
        )
        assert (
            "artifacts.redacted_r7b_export must use the private:<opaque-reference> format"
            in errors
        )
        assert any(line.startswith("known_limitations_review") for line in errors)

    def test_a_record_without_the_r7b_build_is_rejected(self) -> None:
        validator = load_script("validate_p6_readiness")
        document = valid_p6_readiness()
        del document["r7b_build"]
        assert validator.validate_readiness(document) == ["r7b_build must be an object"]

    @pytest.mark.parametrize(
        ("field", "other"),
        [
            ("commit", "d" * 40),
            ("app_image_digest", f"sha256:{'e' * 64}"),
            ("frontend_image_digest", f"sha256:{'f' * 64}"),
        ],
    )
    def test_a_different_build_than_the_release_is_rejected(
        self, field: str, other: str
    ) -> None:
        validator = load_script("validate_p6_readiness")
        document = valid_p6_readiness()
        document["r7b_build"][field] = other
        errors = validator.validate_readiness(document)
        assert len(errors) == 1
        assert errors[0].startswith(f"r7b_build.{field} must equal release.{field}")

    @pytest.mark.parametrize(
        "field", ["commit", "app_image_digest", "frontend_image_digest"]
    )
    @pytest.mark.parametrize("bad", ["", "pending", "ABC", "sha256:short", None])
    def test_a_malformed_build_field_is_rejected(self, field: str, bad: object) -> None:
        validator = load_script("validate_p6_readiness")
        document = valid_p6_readiness()
        document["r7b_build"][field] = bad
        errors = validator.validate_readiness(document)
        assert any(line.startswith(f"r7b_build.{field} must be") for line in errors)

    def test_a_missing_build_field_is_rejected(self) -> None:
        validator = load_script("validate_p6_readiness")
        document = valid_p6_readiness()
        del document["r7b_build"]["commit"]
        errors = validator.validate_readiness(document)
        assert "r7b_build.commit must be a 40-character lowercase Git commit" in errors

    def test_a_non_object_build_is_rejected(self) -> None:
        validator = load_script("validate_p6_readiness")
        document = valid_p6_readiness()
        document["r7b_build"] = "a" * 40
        assert validator.validate_readiness(document) == ["r7b_build must be an object"]

    def test_a_malformed_release_adds_no_equality_noise_for_the_build(self) -> None:
        validator = load_script("validate_p6_readiness")
        document = valid_p6_readiness()
        document["release"] = "x"
        errors = validator.validate_readiness(document)
        assert "release must be an object" in errors
        assert all("must equal" not in line for line in errors)

    def test_the_r7b_export_reference_is_required(self) -> None:
        validator = load_script("validate_p6_readiness")
        document = valid_p6_readiness()
        del document["artifacts"]["redacted_r7b_export"]
        assert validator.validate_readiness(document) == [
            "artifacts.redacted_r7b_export must use the private:<opaque-reference> format"
        ]


class TestLimitationsReview:
    """An empty limitation list needs a recorded review note."""

    @pytest.mark.parametrize("value", [None, "", "  ", "pending", "TBD", 7])
    def test_an_empty_list_without_a_review_note_is_rejected(
        self, value: object
    ) -> None:
        validator = load_script("validate_p6_readiness")
        document = valid_p6_readiness()
        document["known_limitations_review"] = value
        errors = validator.validate_readiness(document)
        assert len(errors) == 1
        assert errors[0].startswith("known_limitations_review must be completed text")

    def test_a_missing_review_note_is_rejected(self) -> None:
        validator = load_script("validate_p6_readiness")
        document = valid_p6_readiness()
        del document["known_limitations_review"]
        assert any(
            line.startswith("known_limitations_review")
            for line in validator.validate_readiness(document)
        )

    def test_the_note_is_not_required_when_limitations_are_listed(self) -> None:
        validator = load_script("validate_p6_readiness")
        document = valid_p6_readiness()
        document["known_limitations"] = [valid_limitation()]
        del document["known_limitations_review"]
        assert validator.validate_readiness(document) == []

    def test_a_malformed_limitations_list_adds_no_review_noise(self) -> None:
        validator = load_script("validate_p6_readiness")
        document = valid_p6_readiness()
        document["known_limitations"] = "none"
        del document["known_limitations_review"]
        errors = validator.validate_readiness(document)
        assert errors == ["known_limitations must be an array"]


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


HARDENING: dict[str, Any] = {
    "read_only": True,
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges:true"],
}


def valid_topology() -> dict[str, Any]:
    """Return the minimum valid rendered production topology."""
    return {
        "services": {
            "app": {
                **HARDENING,
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
                **HARDENING,
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
            "db": {**HARDENING, "networks": {"fragrance_rater-network": None}},
            "backup": {
                **HARDENING,
                "networks": {"fragrance_rater-network": None},
                "healthcheck": {
                    "test": ["CMD", "/scripts/backup_database.sh", "check"]
                },
                "volumes": [
                    {"type": "volume", "source": "backups", "target": "/backups"}
                ],
            },
        },
        "networks": {"authenticated-edge": {"external": True}},
    }


def test_production_topology_accepts_the_short_form_backup_mount() -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"]["backup"]["volumes"] = ["backups:/backups"]

    assert validator.validate_topology(config) == []


def test_production_topology_requires_the_backup_service() -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    del config["services"]["backup"]

    assert validator.validate_topology(config) == [
        "service backup is missing (scheduled database backup, D-18)"
    ]


@pytest.mark.parametrize("healthcheck", [None, {"disable": True}])
def test_production_topology_requires_a_backup_healthcheck(
    healthcheck: dict[str, Any] | None,
) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    if healthcheck is None:
        del config["services"]["backup"]["healthcheck"]
    else:
        config["services"]["backup"]["healthcheck"] = healthcheck

    assert validator.validate_topology(config) == [
        "service backup has no healthcheck, so a stalled job is invisible"
    ]


@pytest.mark.parametrize(
    "volumes", [None, [], [{"type": "volume", "target": "/tmp"}], ["nonsense"]]
)
def test_production_topology_requires_the_backup_volume(volumes: object) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    if volumes is None:
        del config["services"]["backup"]["volumes"]
    else:
        config["services"]["backup"]["volumes"] = volumes

    assert validator.validate_topology(config) == [
        "service backup must keep its dumps in a volume mounted at /backups"
    ]


def test_production_topology_keeps_the_backup_service_off_the_edge_and_the_host() -> (
    None
):
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"]["backup"]["ports"] = [{"published": "5432", "target": 5432}]
    config["services"]["backup"]["networks"]["authenticated-edge"] = None

    assert validator.validate_topology(config) == [
        "service backup publishes a host port",
        "service backup must not join the authenticated-edge network",
    ]


HARDENED_SERVICES = ("app", "frontend", "db", "backup")


@pytest.mark.parametrize("service", HARDENED_SERVICES)
@pytest.mark.parametrize("read_only", [None, False])
def test_production_topology_requires_a_read_only_root_filesystem(
    service: str, read_only: bool | None
) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    if read_only is None:
        del config["services"][service]["read_only"]
    else:
        config["services"][service]["read_only"] = read_only

    assert validator.validate_topology(config) == [
        f"service {service} must set read_only: true"
    ]


@pytest.mark.parametrize("service", HARDENED_SERVICES)
@pytest.mark.parametrize("cap_drop", [None, [], ["NET_RAW"]])
def test_production_topology_requires_every_capability_dropped(
    service: str, cap_drop: list[str] | None
) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    if cap_drop is None:
        del config["services"][service]["cap_drop"]
    else:
        config["services"][service]["cap_drop"] = cap_drop

    assert validator.validate_topology(config) == [
        f"service {service} must set cap_drop: [ALL]"
    ]


@pytest.mark.parametrize("service", HARDENED_SERVICES)
@pytest.mark.parametrize("security_opt", [None, [], ["seccomp=unconfined"]])
def test_production_topology_requires_no_new_privileges(
    service: str, security_opt: list[str] | None
) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    if security_opt is None:
        del config["services"][service]["security_opt"]
    else:
        config["services"][service]["security_opt"] = security_opt

    assert validator.validate_topology(config) == [
        f"service {service} must set no-new-privileges:true"
    ]


@pytest.mark.parametrize("service", HARDENED_SERVICES)
@pytest.mark.parametrize("option", ["no-new-privileges:true", "no-new-privileges=true"])
def test_production_topology_accepts_either_no_new_privileges_spelling(
    service: str, option: str
) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"][service]["security_opt"] = [option]

    assert validator.validate_topology(config) == []


@pytest.mark.parametrize("service", HARDENED_SERVICES)
def test_production_topology_accepts_a_narrow_capability_added_back(
    service: str,
) -> None:
    """The smallest working set is allowed; only the broad ones are refused."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"][service]["cap_add"] = ["CHOWN", "SETUID"]

    assert validator.validate_topology(config) == []


@pytest.mark.parametrize("service", HARDENED_SERVICES)
@pytest.mark.parametrize(
    "capability",
    [
        "ALL",
        "all",
        "SYS_ADMIN",
        "CAP_SYS_ADMIN",
        "cap_sys_admin",
        "SYS_MODULE",
        "SYS_PTRACE",
        "SYS_RAWIO",
        "DAC_READ_SEARCH",
        "NET_ADMIN",
        "BPF",
    ],
)
def test_production_topology_rejects_a_broad_capability_added_back(
    service: str, capability: str
) -> None:
    """Docker reads ``CAP_SYS_ADMIN`` and ``sys_admin`` as the same capability."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"][service]["cap_add"] = ["CHOWN", capability]
    named = capability.upper().removeprefix("CAP_")

    assert validator.validate_topology(config) == [
        f"service {service} adds a broad capability ({named})"
    ]


@pytest.mark.parametrize("cap_drop", [["CAP_ALL"], ["cap_all"]])
def test_production_topology_accepts_a_prefixed_cap_drop_all(
    cap_drop: list[str],
) -> None:
    """Docker normalises the ``CAP_`` prefix away, so this spelling drops everything."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"]["app"]["cap_drop"] = cap_drop

    assert validator.validate_topology(config) == []


@pytest.mark.parametrize("service", HARDENED_SERVICES)
def test_production_topology_rejects_a_contradictory_no_new_privileges(
    service: str,
) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"][service]["security_opt"] = [
        "no-new-privileges:true",
        "no-new-privileges:false",
    ]

    assert validator.validate_topology(config) == [
        f"service {service} must set no-new-privileges:true"
    ]


@pytest.mark.parametrize("service", HARDENED_SERVICES)
def test_production_topology_rejects_a_privileged_service(service: str) -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"][service]["privileged"] = True

    assert validator.validate_topology(config) == [
        f"service {service} must not run privileged"
    ]


def test_production_topology_reports_every_missing_control_on_a_bare_service() -> None:
    validator = load_script("validate_production_topology")
    config = valid_topology()
    for control in HARDENING:
        del config["services"]["db"][control]

    assert validator.validate_topology(config) == [
        "service db must set read_only: true",
        "service db must set cap_drop: [ALL]",
        "service db must set no-new-privileges:true",
    ]


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


@pytest.mark.parametrize("capability", ["DAC_OVERRIDE", "CAP_DAC_OVERRIDE"])
def test_production_topology_rejects_dac_override_on_backup_only(
    capability: str,
) -> None:
    """The backup script's file modes are its boundary; db may repair ownership."""
    validator = load_script("validate_production_topology")
    config = valid_topology()
    config["services"]["backup"]["cap_add"] = [capability]
    config["services"]["db"]["cap_add"] = ["CHOWN", "DAC_OVERRIDE"]

    assert validator.validate_topology(config) == [
        "service backup adds a broad capability (DAC_OVERRIDE)"
    ]
