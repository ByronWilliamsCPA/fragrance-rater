"""Tests for ``scripts/check_type_baseline.py``, the BasedPyright ratchet gate."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).parents[3]


def load_script() -> ModuleType:
    """Load the gate script as a module."""
    path = ROOT / "scripts" / "check_type_baseline.py"
    spec = importlib.util.spec_from_file_location("check_type_baseline", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load_script()


def report(errors: int, warnings: int) -> dict[str, object]:
    """Build the part of a BasedPyright JSON report the gate reads."""
    return {"summary": {"errorCount": errors, "warningCount": warnings}}


def write(tmp_path: Path, payload: object) -> str:
    """Write a JSON report to disk and return its path."""
    path = tmp_path / "basedpyright.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


class TestEvaluate:
    """The comparison between a report and the ceiling."""

    def test_at_ceiling_passes_without_a_hint(self) -> None:
        code, messages = gate.evaluate(0, 10, 10)
        assert code == gate.EXIT_OK
        assert len(messages) == 1
        assert "ceiling 10" in messages[0]

    def test_below_ceiling_passes_and_says_to_lower_it(self) -> None:
        code, messages = gate.evaluate(0, 7, 10)
        assert code == gate.EXIT_OK
        assert any("lower WARNING_CEILING to 7" in line for line in messages)

    def test_one_warning_over_the_ceiling_fails(self) -> None:
        code, messages = gate.evaluate(0, 11, 10)
        assert code == gate.EXIT_REGRESSION
        assert "rose to 11" in messages[0]

    def test_any_error_fails_even_under_the_ceiling(self) -> None:
        code, messages = gate.evaluate(1, 0, 10)
        assert code == gate.EXIT_REGRESSION
        assert "1 error" in messages[0]

    def test_errors_and_warnings_both_reported(self) -> None:
        code, messages = gate.evaluate(2, 99, 10)
        assert code == gate.EXIT_REGRESSION
        assert any("2 error" in line for line in messages)
        assert any("rose to 99" in line for line in messages)


class TestReadCounts:
    """Parsing the report shape, failing closed on anything unexpected."""

    def test_reads_the_two_counts(self) -> None:
        assert gate.read_counts(report(3, 4)) == (3, 4)

    @pytest.mark.parametrize(
        "payload",
        [
            [],
            "text",
            {},
            {"summary": []},
            {"summary": {"errorCount": 0}},
            {"summary": {"warningCount": 0}},
            {"summary": {"errorCount": "0", "warningCount": 0}},
            {"summary": {"errorCount": 0, "warningCount": -1}},
            {"summary": {"errorCount": True, "warningCount": 0}},
            {"summary": {"errorCount": 0, "warningCount": 1.5}},
        ],
    )
    def test_rejects_a_malformed_report(self, payload: object) -> None:
        with pytest.raises(gate.BadReportError):
            gate.read_counts(payload)


class TestMain:
    """End to end: file and standard-input sources and their exit codes."""

    def test_passes_for_a_report_at_the_default_ceiling(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = write(tmp_path, report(0, gate.WARNING_CEILING))
        assert gate.main([path]) == gate.EXIT_OK
        assert "0 errors" in capsys.readouterr().out

    def test_fails_when_one_warning_over_the_default_ceiling(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = write(tmp_path, report(0, gate.WARNING_CEILING + 1))
        assert gate.main([path]) == gate.EXIT_REGRESSION
        assert "rose to" in capsys.readouterr().err

    def test_ceiling_option_overrides_the_default(self, tmp_path: Path) -> None:
        path = write(tmp_path, report(0, 5))
        assert gate.main([path, "--ceiling", "5"]) == gate.EXIT_OK
        assert gate.main([path, "--ceiling", "4"]) == gate.EXIT_REGRESSION

    def test_reads_standard_input_for_a_dash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(report(0, 1))))
        assert gate.main(["-", "--ceiling", "1"]) == gate.EXIT_OK

    def test_missing_file_is_a_bad_report_not_a_pass(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = gate.main([str(tmp_path / "absent.json")])
        assert code == gate.EXIT_BAD_REPORT
        assert "could not read" in capsys.readouterr().err

    def test_invalid_json_is_a_bad_report_not_a_pass(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        assert gate.main([str(path)]) == gate.EXIT_BAD_REPORT

    def test_empty_standard_input_is_a_bad_report(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        assert gate.main(["-"]) == gate.EXIT_BAD_REPORT

    def test_the_committed_ceiling_matches_a_real_report_shape(self) -> None:
        """The ceiling is a non-negative integer the report comparison can use."""
        assert isinstance(gate.WARNING_CEILING, int)
        assert gate.WARNING_CEILING >= 0
