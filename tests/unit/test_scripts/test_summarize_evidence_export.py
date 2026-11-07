"""Tests for ``scripts/summarize_evidence_export.py``, the R7b export summary."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from fragrance_rater.services.evidence_export import CAPTURED_FIELDS, EXPORT_VERSION

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).parents[3]
BUILD = "0123456789abcdef0123456789abcdef01234567"


def load_script() -> ModuleType:
    """Load the summary script as a module."""
    path = ROOT / "scripts" / "summarize_evidence_export.py"
    spec = importlib.util.spec_from_file_location("summarize_evidence_export", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve string annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = load_script()


def _row(section: str, **overrides: object) -> dict[str, Any]:
    """Return a row with every captured field of ``section`` non-null."""
    row: dict[str, Any] = dict.fromkeys(CAPTURED_FIELDS[section], "value")
    row.update(overrides)
    return row


def make_export(instrument: str = BUILD) -> dict[str, Any]:
    """Build a complete export: one session, two presentations, three observations."""
    skin = _row(
        "observation",
        stage="SKIN",
        fit_choices={"season": ["spring"], "setting": ["home"]},
    )
    blotter = _row(
        "observation",
        stage="BLOTTER",
        fit_choices={"season": [], "setting": []},
    )
    skin_without_fit = _row(
        "observation",
        stage="SKIN",
        fit_choices={"season": [], "setting": ["home"]},
    )
    return {
        "export_version": EXPORT_VERSION,
        "program": _row("program", instrument_version=instrument),
        "enrollment": _row("enrollment"),
        "consent": {"state": {}, "events": [{"scope": "a"}, {"scope": "b"}]},
        "sessions": [
            {
                **_row("session"),
                "context": _row("context"),
                "context_withheld": False,
                "presentations": [
                    {**_row("presentation"), "observations": [skin, blotter]},
                    {**_row("presentation"), "observations": [skin_without_fit]},
                ],
                "rankings": [{"entries": [_row("rank_entry"), _row("rank_entry")]}],
                "quality_flags": [_row("flag")],
            }
        ],
    }


def write(tmp_path: Path, export: object, name: str = "export.json") -> Path:
    """Write an export to disk and return its path."""
    path = tmp_path / name
    path.write_text(json.dumps(export), encoding="utf-8")
    return path


def summarize(*exports: dict[str, Any]) -> Any:
    """Return the pooled summary of already-validated exports."""
    summary = tool.Summary()
    for export in exports:
        tool.add_export(summary, tool.read_export(export))
    return summary


class TestCounts:
    """The pooled non-null counts and their denominators."""

    def test_every_captured_field_is_counted(self) -> None:
        summary = summarize(make_export())
        for section, names in CAPTURED_FIELDS.items():
            assert set(summary.fields[section]) == set(names)

    def test_denominators_are_the_rows_that_could_carry_the_field(self) -> None:
        summary = summarize(make_export())
        assert summary.fields["program"]["instrument_version"].denominator == 1
        assert summary.fields["session"]["occurred_on"].denominator == 1
        assert summary.fields["presentation"]["applied_at"].denominator == 2
        assert summary.fields["observation"]["observed_at"].denominator == 3
        assert summary.fields["rank_entry"]["rank_position"].denominator == 2
        assert summary.fields["flag"]["code"].denominator == 1

    def test_fit_is_counted_against_skin_stage_observations_only(self) -> None:
        summary = summarize(make_export())
        # Two skin rows; the blotter row is excluded from both denominators.
        assert (summary.fit["season"].non_null, summary.fit["season"].denominator) == (
            1,
            2,
        )
        assert (
            summary.fit["setting"].non_null,
            summary.fit["setting"].denominator,
        ) == (2, 2)

    def test_a_null_counts_in_the_denominator_but_not_the_numerator(self) -> None:
        export = make_export()
        export["sessions"][0]["presentations"][0]["observations"][0]["observed_at"] = (
            None
        )
        tally = summarize(export).fields["observation"]["observed_at"]
        assert (tally.non_null, tally.denominator) == (2, 3)

    def test_false_and_zero_are_values_not_nulls(self) -> None:
        export = make_export()
        observation = export["sessions"][0]["presentations"][0]["observations"][0]
        observation["scrubbed_off"] = False
        observation["time_to_scrub_minutes"] = 0
        fields = summarize(export).fields["observation"]
        assert fields["scrubbed_off"].non_null == 3
        assert fields["time_to_scrub_minutes"].non_null == 3

    def test_flags_and_consent_events_are_counted(self) -> None:
        summary = summarize(make_export())
        assert summary.quality_flags == 1
        assert summary.consent_events == 2

    def test_withheld_context_is_counted_and_is_null(self) -> None:
        export = make_export()
        export["sessions"][0]["context"] = None
        export["sessions"][0]["context_withheld"] = True
        summary = summarize(export)
        assert summary.context_withheld_sessions == 1
        assert summary.fields["context"]["illness"].non_null == 0
        assert summary.fields["context"]["illness"].denominator == 1

    def test_exports_are_pooled(self) -> None:
        summary = summarize(make_export(), make_export())
        assert summary.fields["program"]["instrument_version"].denominator == 2
        assert summary.fit["season"].denominator == 4
        assert summary.quality_flags == 2
        assert summary.consent_events == 4

    def test_an_export_without_sessions_counts_zero_rows(self) -> None:
        export = make_export()
        export["sessions"] = []
        summary = summarize(export)
        assert summary.fields["session"]["occurred_on"].denominator == 0
        assert summary.fit["season"].denominator == 0


class TestRequirements:
    """The pass and fail conditions."""

    def test_a_complete_export_has_no_problems(self) -> None:
        problems = tool.check_requirements(
            summarize(make_export()), each_field_once=True, expect_instrument=BUILD
        )
        assert problems == []

    def test_a_field_null_everywhere_is_named(self) -> None:
        export = make_export()
        for presentation in export["sessions"][0]["presentations"]:
            presentation["sample_batch_code"] = None
        problems = tool.check_requirements(
            summarize(export), each_field_once=True, expect_instrument=None
        )
        assert problems == ["presentation.sample_batch_code is null in every row (0/2)"]

    def test_no_option_means_no_field_requirement(self) -> None:
        export = make_export()
        export["enrollment"]["randomization_algorithm"] = None
        assert (
            tool.check_requirements(
                summarize(export), each_field_once=False, expect_instrument=None
            )
            == []
        )

    def test_a_different_instrument_version_fails(self) -> None:
        problems = tool.check_requirements(
            summarize(make_export("other-build")),
            each_field_once=False,
            expect_instrument=BUILD,
        )
        assert len(problems) == 1
        assert "'other-build'" in problems[0]

    def test_an_unpinned_fallback_fails_even_when_it_is_the_expected_value(
        self,
    ) -> None:
        unpinned = f"{tool.UNPINNED_INSTRUMENT_PREFIX}0.1.0"
        problems = tool.check_requirements(
            summarize(make_export(unpinned)),
            each_field_once=False,
            expect_instrument=unpinned,
        )
        assert any("unpinned fallback" in line for line in problems)

    def test_a_null_instrument_version_fails_the_pin(self) -> None:
        export = make_export()
        export["program"]["instrument_version"] = None
        problems = tool.check_requirements(
            summarize(export), each_field_once=False, expect_instrument=BUILD
        )
        assert problems == ["program.instrument_version is null in every export"]


class TestReadExport:
    """Anything that is not an export of this version is rejected."""

    @pytest.mark.parametrize("payload", [[], "text", {}, {"export_version": "v0"}])
    def test_rejects_a_document_of_the_wrong_version_or_shape(
        self, payload: object
    ) -> None:
        with pytest.raises(tool.BadExportError):
            tool.read_export(payload)

    @pytest.mark.parametrize(
        "mutate",
        [
            lambda e: e.pop("program"),
            lambda e: e.update(sessions="x"),
            lambda e: e.update(consent=[]),
            lambda e: e["sessions"].append(5),
            lambda e: e["sessions"][0].update(presentations={}),
            lambda e: e["sessions"][0]["presentations"][0].update(observations=None),
            lambda e: e["sessions"][0]["presentations"][0]["observations"][0].pop(
                "fit_choices"
            ),
            lambda e: e["sessions"][0].update(rankings=[{"entries": 3}]),
        ],
    )
    def test_a_malformed_body_is_a_bad_export_not_a_traceback(
        self, mutate: Any
    ) -> None:
        export = copy.deepcopy(make_export())
        mutate(export)
        with pytest.raises(tool.BadExportError):
            summarize(export)


class TestMain:
    """End to end: files, exit codes and output."""

    def test_a_readable_export_exits_zero_and_prints_counts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = write(tmp_path, make_export())
        assert tool.main([str(path)]) == tool.EXIT_OK
        out = capsys.readouterr().out
        assert "observation:" in out
        assert "observed_at: 3/3" in out
        assert "season_fit: 1/2" in out
        assert "quality flags: 1" in out

    def test_the_file_hash_and_size_are_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = write(tmp_path, make_export())
        raw = path.read_bytes()
        assert tool.main([str(path), "--json"]) == tool.EXIT_OK
        report = json.loads(capsys.readouterr().out)
        assert report["files"] == [
            {
                "file": "export.json",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
        ]
        assert report["fit_choices_skin_stage_only"]["season"] == {
            "non_null": 1,
            "denominator": 2,
        }

    def test_a_missing_field_exits_one_and_names_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        export = make_export()
        export["sessions"][0]["quality_flags"][0]["explanation"] = None
        path = write(tmp_path, export)
        assert (
            tool.main([str(path), "--require-each-field-once"]) == tool.EXIT_REQUIREMENT
        )
        assert "flag.explanation" in capsys.readouterr().err

    def test_the_instrument_pin_is_checked(self, tmp_path: Path) -> None:
        path = write(tmp_path, make_export())
        assert tool.main([str(path), "--expect-instrument", BUILD]) == tool.EXIT_OK
        assert (
            tool.main([str(path), "--expect-instrument", "nope"])
            == tool.EXIT_REQUIREMENT
        )

    def test_several_files_are_pooled(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        first = write(tmp_path, make_export(), "a.json")
        second = write(tmp_path, make_export(), "b.json")
        assert tool.main([str(first), str(second)]) == tool.EXIT_OK
        out = capsys.readouterr().out
        assert "2 export(s)" in out
        assert "observed_at: 6/6" in out

    def test_an_unreadable_file_exits_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert tool.main([str(tmp_path / "absent.json")]) == tool.EXIT_BAD_EXPORT
        assert "could not read" in capsys.readouterr().err
        broken = tmp_path / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        assert tool.main([str(broken)]) == tool.EXIT_BAD_EXPORT
        binary = tmp_path / "binary.json"
        binary.write_bytes(b"\xff\xfe\x00")
        assert tool.main([str(binary)]) == tool.EXIT_BAD_EXPORT

    def test_a_wrong_version_exits_two(self, tmp_path: Path) -> None:
        export = make_export()
        export["export_version"] = "r7b-evidence-v0"
        assert tool.main([str(write(tmp_path, export))]) == tool.EXIT_BAD_EXPORT

    def test_one_bad_file_among_good_ones_fails_the_run(self, tmp_path: Path) -> None:
        good = write(tmp_path, make_export(), "good.json")
        bad = write(tmp_path, [], "bad.json")
        assert tool.main([str(good), str(bad)]) == tool.EXIT_BAD_EXPORT
