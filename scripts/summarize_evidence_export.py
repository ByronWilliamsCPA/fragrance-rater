#!/usr/bin/env python3
"""Summarize saved R7b evidence exports for the P6.3 rehearsal and the F1 gate.

The manager-only ``evidence-export`` endpoint has no screen, so an operator saves
its JSON. ``docs/planning/gates/f1.md`` asks for per-field non-null counts with
denominators across all four evaluators, ``season_fit`` and ``setting_fit``
counted against skin-stage observations only, and counts of quality flags and
consent records. This reads one or more saved exports and prints exactly that.

The field lists come from ``fragrance_rater.services.evidence_export``, the module
that builds the export, so this report cannot drift from what the export carries.
Run it with ``uv run`` so that module imports.

Usage:
    uv run python scripts/summarize_evidence_export.py export.json [more.json ...]
    uv run python scripts/summarize_evidence_export.py --require-each-field-once \\
        --expect-instrument <build sha or release tag> export.json
    uv run python scripts/summarize_evidence_export.py --json export.json > report.json

Exit codes:
    0: every requirement holds (with no option, any readable export passes)
    1: a requirement failed (export version, instrument pin, or a field that is
       null in every row while ``--require-each-field-once`` is given)
    2: a file could not be read or is not an evidence export
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from fragrance_rater.services.calibration_service import UNPINNED_INSTRUMENT_PREFIX
from fragrance_rater.services.evidence_export import CAPTURED_FIELDS, EXPORT_VERSION

EXIT_OK = 0
EXIT_REQUIREMENT = 1
EXIT_BAD_EXPORT = 2

# Season and setting fit are child rows, not columns, and only skin-stage
# observations are eligible for them (blotter rows are excluded).
FIT_DIMENSIONS = ("season", "setting")
SKIN_STAGE = "SKIN"


class BadExportError(ValueError):
    """Raised when a file is not a usable evidence export."""


@dataclass
class Tally:
    """Non-null count against the number of rows that could carry the value."""

    non_null: int = 0
    denominator: int = 0

    def add(self, present: bool) -> None:
        """Count one row."""
        self.denominator += 1
        self.non_null += int(present)

    def merge(self, other: Tally) -> None:
        """Fold another tally into this one."""
        self.non_null += other.non_null
        self.denominator += other.denominator


@dataclass
class Summary:
    """Counts pooled over every export given."""

    fields: dict[str, dict[str, Tally]] = field(default_factory=dict)
    fit: dict[str, Tally] = field(default_factory=dict)
    quality_flags: int = 0
    consent_events: int = 0
    context_withheld_sessions: int = 0
    instrument_versions: set[str] = field(default_factory=set)
    files: list[dict[str, object]] = field(default_factory=list)

    def tally(self, section: str, name: str) -> Tally:
        """Return the tally for one field, creating it on first use."""
        return self.fields.setdefault(section, {}).setdefault(name, Tally())


def _object(value: object, where: str) -> dict[str, object]:
    """Return ``value`` as a JSON object or raise ``BadExportError``."""
    if not isinstance(value, dict):
        msg = f"{where} is missing or not an object"
        raise BadExportError(msg)
    return cast("dict[str, object]", value)


def _rows(value: object, where: str) -> list[dict[str, object]]:
    """Return ``value`` as a list of JSON objects or raise ``BadExportError``."""
    if not isinstance(value, list):
        msg = f"{where} is missing or not a list"
        raise BadExportError(msg)
    rows: list[dict[str, object]] = []
    for index, row in enumerate(cast("list[object]", value)):
        rows.append(_object(row, f"{where}[{index}]"))
    return rows


def _count_fields(
    summary: Summary, section: str, rows: list[dict[str, object]]
) -> None:
    """Tally every captured field of ``section`` over ``rows``."""
    for name in CAPTURED_FIELDS[section]:
        tally = summary.tally(section, name)
        for row in rows:
            tally.add(row.get(name) is not None)


def read_export(document: object) -> dict[str, object]:
    """Check the export version and return the document as an object."""
    export = _object(document, "the export")
    version = export.get("export_version")
    if version != EXPORT_VERSION:
        msg = f"export_version is {version!r}, expected {EXPORT_VERSION!r}"
        raise BadExportError(msg)
    return export


def add_export(summary: Summary, export: dict[str, object]) -> None:
    """Fold one export's counts into ``summary``."""
    program = _object(export.get("program"), "program")
    enrollment = _object(export.get("enrollment"), "enrollment")
    consent = _object(export.get("consent"), "consent")
    sessions = _rows(export.get("sessions"), "sessions")

    presentations: list[dict[str, object]] = []
    observations: list[dict[str, object]] = []
    rank_entries: list[dict[str, object]] = []
    flags: list[dict[str, object]] = []
    contexts: list[dict[str, object]] = []
    for session in sessions:
        context = session.get("context")
        contexts.append(_object(context, "context") if context is not None else {})
        if session.get("context_withheld") is True:
            summary.context_withheld_sessions += 1
        session_presentations = _rows(session.get("presentations"), "presentations")
        presentations.extend(session_presentations)
        for presentation in session_presentations:
            observations.extend(_rows(presentation.get("observations"), "observations"))
        for ranking in _rows(session.get("rankings"), "rankings"):
            rank_entries.extend(_rows(ranking.get("entries"), "rankings.entries"))
        flags.extend(_rows(session.get("quality_flags"), "quality_flags"))

    _count_fields(summary, "program", [program])
    _count_fields(summary, "enrollment", [enrollment])
    _count_fields(summary, "session", sessions)
    _count_fields(summary, "context", contexts)
    _count_fields(summary, "presentation", presentations)
    _count_fields(summary, "observation", observations)
    _count_fields(summary, "rank_entry", rank_entries)
    _count_fields(summary, "flag", flags)

    for dimension in FIT_DIMENSIONS:
        tally = summary.fit.setdefault(dimension, Tally())
        for observation in observations:
            if observation.get("stage") != SKIN_STAGE:
                continue
            choices = _object(observation.get("fit_choices"), "fit_choices")
            ticked = cast("object", choices.get(dimension))
            tally.add(
                isinstance(ticked, list) and len(cast("list[object]", ticked)) > 0
            )

    summary.quality_flags += len(flags)
    summary.consent_events += len(_rows(consent.get("events"), "consent.events"))
    instrument = program.get("instrument_version")
    if isinstance(instrument, str):
        summary.instrument_versions.add(instrument)


def load(path: Path) -> tuple[dict[str, object], dict[str, object]]:
    """Read one export file; return its document and its hash record."""
    try:
        raw = path.read_bytes()
        document = cast("object", json.loads(raw.decode("utf-8")))
    except (OSError, ValueError) as exc:
        msg = f"could not read a JSON export from {str(path)!r}: {exc}"
        raise BadExportError(msg) from exc
    record: dict[str, object] = {
        "file": path.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    try:
        return read_export(document), record
    except BadExportError as exc:
        msg = f"{str(path)!r}: {exc}"
        raise BadExportError(msg) from exc


def check_requirements(
    summary: Summary, *, each_field_once: bool, expect_instrument: str | None
) -> list[str]:
    """Return one line per failed requirement."""
    problems: list[str] = []
    if each_field_once:
        problems.extend(
            f"{section}.{name} is null in every row ({tally.non_null}/{tally.denominator})"
            for section, names in summary.fields.items()
            for name, tally in names.items()
            if tally.non_null == 0
        )
    if expect_instrument is not None:
        pinned = summary.instrument_versions
        label = "program.instrument_version"
        if not pinned:
            problems.append(f"{label} is null in every export")
        problems.extend(
            f"{label} {version!r} is not the expected {expect_instrument!r}"
            for version in sorted(pinned - {expect_instrument})
        )
        problems.extend(
            f"{label} {version!r} is an unpinned fallback, not a build identifier"
            for version in sorted(pinned)
            if version.startswith(UNPINNED_INSTRUMENT_PREFIX)
        )
    return problems


def as_document(summary: Summary) -> dict[str, object]:
    """Return the summary as a JSON-ready report."""

    def render(tally: Tally) -> dict[str, int]:
        return {"non_null": tally.non_null, "denominator": tally.denominator}

    return {
        "export_version": EXPORT_VERSION,
        "files": summary.files,
        "fields": {
            section: {name: render(tally) for name, tally in names.items()}
            for section, names in summary.fields.items()
        },
        "fit_choices_skin_stage_only": {
            dimension: render(tally) for dimension, tally in summary.fit.items()
        },
        "quality_flags": summary.quality_flags,
        "consent_events": summary.consent_events,
        "sessions_with_context_withheld": summary.context_withheld_sessions,
        "instrument_versions": sorted(summary.instrument_versions),
    }


def render_text(summary: Summary) -> list[str]:
    """Return the summary as plain lines for a terminal."""
    lines = [f"{len(summary.files)} export(s), version {EXPORT_VERSION}"]
    lines.extend(
        f"  {item['file']}: {item['bytes']} bytes, sha256 {item['sha256']}"
        for item in summary.files
    )
    for section, names in summary.fields.items():
        lines.append(f"{section}:")
        lines.extend(
            f"  {name}: {tally.non_null}/{tally.denominator}"
            for name, tally in names.items()
        )
    lines.append("fit choices (skin-stage observations only):")
    lines.extend(
        f"  {dimension}_fit: {tally.non_null}/{tally.denominator}"
        for dimension, tally in summary.fit.items()
    )
    lines.append(f"quality flags: {summary.quality_flags}")
    lines.append(f"consent events: {summary.consent_events}")
    lines.append(f"sessions with context withheld: {summary.context_withheld_sessions}")
    lines.append(
        "instrument versions: "
        + (", ".join(sorted(summary.instrument_versions)) or "none")
    )
    return lines


class _Args(argparse.Namespace):
    """Typed view of the parsed command line."""

    exports: list[Path] = []
    require_each_field_once: bool = False
    expect_instrument: str | None = None
    json: bool = False


def main(argv: list[str] | None = None) -> int:
    """Summarize the exports and return the process exit code."""
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n", maxsplit=1)[0],
    )
    parser.add_argument("exports", nargs="+", type=Path, help="saved export JSON files")
    parser.add_argument(
        "--require-each-field-once",
        action="store_true",
        help="fail when a captured field is null in every row (R7b acceptance)",
    )
    parser.add_argument(
        "--expect-instrument",
        metavar="BUILD",
        help="fail unless every program records this instrument version",
    )
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv, namespace=_Args())

    summary = Summary()
    try:
        for path in args.exports:
            export, record = load(path)
            summary.files.append(record)
            add_export(summary, export)
    except BadExportError as exc:
        sys.stderr.write(f"summarize_evidence_export: {exc}\n")
        return EXIT_BAD_EXPORT

    if args.json:
        sys.stdout.write(json.dumps(as_document(summary), indent=2) + "\n")
    else:
        sys.stdout.write("\n".join(render_text(summary)) + "\n")
    problems = check_requirements(
        summary,
        each_field_once=args.require_each_field_once,
        expect_instrument=args.expect_instrument,
    )
    for problem in problems:
        sys.stderr.write(f"{problem}\n")
    return EXIT_REQUIREMENT if problems else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
