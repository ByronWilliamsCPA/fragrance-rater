#!/usr/bin/env python3
"""Fail when BasedPyright reports errors or more warnings than the ratchet allows.

CLAUDE.md says the BasedPyright warning count must not rise, but the shared CI
workflow only emits a ``::warning::`` when type checking finds issues, so
nothing enforced it. This script is the repository-local gate: it reads the
JSON that ``basedpyright --outputjson`` prints and compares its summary with
``WARNING_CEILING``.

Usage:
    uv run basedpyright src/ --outputjson > basedpyright.json || true
    uv run python scripts/check_type_baseline.py basedpyright.json

    # or from standard input
    uv run basedpyright src/ --outputjson | uv run python scripts/check_type_baseline.py -

Exit codes:
    0: no errors and the warning count is at or below the ceiling
    1: errors were reported, or the warning count rose above the ceiling
    2: the report could not be read or did not have the expected shape

The ceiling only moves down. When a change removes warnings, lower
``WARNING_CEILING`` in the same change; the script prints the new value to use.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

# Measured with ``uv run basedpyright src/`` on main at 381d33c (2026-11-07):
# 0 errors, 131 warnings. Lower this when warnings are fixed; never raise it.
WARNING_CEILING = 131

EXIT_OK = 0
EXIT_REGRESSION = 1
EXIT_BAD_REPORT = 2


class BadReportError(ValueError):
    """Raised when the BasedPyright JSON report is not usable."""


def _count(summary: dict[str, object], key: str) -> int:
    """Return one non-negative integer count from the report summary."""
    value = summary.get(key)
    # bool is an int subclass; a boolean count is a malformed report, not a count.
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        msg = f"summary.{key} is missing or not a non-negative integer: {value!r}"
        raise BadReportError(msg)
    return value


def read_counts(report: object) -> tuple[int, int]:
    """Return ``(errors, warnings)`` from a parsed BasedPyright report."""
    if not isinstance(report, dict):
        msg = "the report is not a JSON object"
        raise BadReportError(msg)
    summary: object = cast("dict[str, object]", report).get("summary")
    if not isinstance(summary, dict):
        msg = "the report has no 'summary' object"
        raise BadReportError(msg)
    counts = cast("dict[str, object]", summary)
    return _count(counts, "errorCount"), _count(counts, "warningCount")


def evaluate(errors: int, warnings: int, ceiling: int) -> tuple[int, list[str]]:
    """Compare the counts with the ceiling and return ``(exit_code, messages)``."""
    messages: list[str] = []
    code = EXIT_OK
    if errors > 0:
        messages.append(f"BasedPyright reports {errors} error(s); the baseline is 0.")
        code = EXIT_REGRESSION
    if warnings > ceiling:
        messages.append(
            f"BasedPyright warnings rose to {warnings}, above the ceiling of {ceiling}.",
        )
        messages.append("Fix the new warnings; do not raise the ceiling.")
        code = EXIT_REGRESSION
    if code == EXIT_OK:
        messages.append(
            f"BasedPyright: 0 errors, {warnings} warning(s) (ceiling {ceiling}).",
        )
        if warnings < ceiling:
            messages.append(
                f"Below the ceiling: lower WARNING_CEILING to {warnings} in this file.",
            )
    return code, messages


def _load(source: str) -> object:
    """Parse the JSON report from a file path, or from standard input for ``-``."""
    try:
        text = sys.stdin.read() if source == "-" else Path(source).read_text("utf-8")
        report = cast("object", json.loads(text))
    # JSONDecodeError and UnicodeDecodeError are both ValueError subclasses, so
    # malformed JSON and non-UTF-8 bytes are both reported as a bad report.
    except (OSError, ValueError) as exc:
        msg = f"could not read a JSON report from {source!r}: {exc}"
        raise BadReportError(msg) from exc
    return report


def _non_negative_int(value: str) -> int:
    """Parse a command-line integer that must not be negative."""
    try:
        number = int(value)
    except ValueError as exc:
        msg = f"{value!r} is not an integer"
        raise argparse.ArgumentTypeError(msg) from exc
    if number < 0:
        msg = f"{value!r} is negative; a warning ceiling cannot be below 0"
        raise argparse.ArgumentTypeError(msg)
    return number


class _Args(argparse.Namespace):
    """Typed view of the parsed command line."""

    report: str = ""
    ceiling: int = WARNING_CEILING


def main(argv: list[str] | None = None) -> int:
    """Run the gate and return the process exit code."""
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n", maxsplit=1)[0],
    )
    parser.add_argument(
        "report",
        help="path to the `basedpyright --outputjson` file, or '-' for standard input",
    )
    parser.add_argument(
        "--ceiling",
        type=_non_negative_int,
        default=WARNING_CEILING,
        help=f"warning ceiling to enforce (default: {WARNING_CEILING})",
    )
    args = parser.parse_args(argv, namespace=_Args())

    try:
        errors, warnings = read_counts(_load(args.report))
    except BadReportError as exc:
        sys.stderr.write(f"check_type_baseline: {exc}\n")
        return EXIT_BAD_REPORT

    code, messages = evaluate(errors, warnings, args.ceiling)
    stream = sys.stdout if code == EXIT_OK else sys.stderr
    for line in messages:
        stream.write(f"{line}\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
