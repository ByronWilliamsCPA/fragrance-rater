"""Build facilitator spray sheets and per-evaluator blind-code headers from a local mapping.

The facilitator in a six-evaluator session sprays vials onto coded blotters and
hands one tray of three to each evaluator. This tool turns the facilitator's
private mapping into two kinds of output:

* Facilitator-only spray sheets (one per session) that list, per vial, which
  blind code goes on which evaluator's tray and position, plus the same data per
  evaluator tray, with blank time columns. These carry vial numbers and must
  never leave the facilitator's hands.
* Evaluator-facing header files (one per evaluator per session) carrying only
  the sheet version, a random paper record ID, the evaluator reference and the
  three blind codes in tray order. These never carry a vial number, a session
  key, or any identity. The paper record ID links the score sheet to the
  separate conditions slip and is random, so it reveals nothing.

A facilitator-only index (``paper-record-index.csv``) maps each paper record ID
back to the evaluator reference and session key. It also stays private.

Input format (a CSV with a header row, or a JSON list of objects with the same
keys). One row per evaluator tray position:

    session,vial,evaluator,position,blind_code[,persistent][,paper_record_id]

* ``session``: the facilitator's private key for the sitting (any non-empty
  text). It is used only on facilitator-only output.
* ``vial``: the vial number the facilitator sprays from (any non-empty text).
* ``evaluator``: an opaque evaluator reference such as ``E1``. Never a name.
* ``position``: 1-based tray position for that evaluator in that session.
* ``blind_code``: the code printed on the blotter, exactly as the application
  holds it (the enrollment's physical blind code). The code is not generated
  here, because a code that differs from the application's would defeat the
  transcription check.
* ``persistent`` (optional): ``yes`` marks a persistent or aversive vial, so the
  spray sheet reminds the facilitator to extend clean air to about 5 minutes.
* ``paper_record_id`` (optional): reuse an existing paper record ID; otherwise a
  random one is generated for each evaluator and session.

Within one session every evaluator must hold the same set of vials (shared
triples) in a full tray of ``--tray-size`` positions, positions must be
``1..tray-size`` with no gaps, and blind codes must be unique across the file.

Usage:
    uv run python scripts/make_spray_sheets.py --mapping /secure/mapping.csv \\
        [--output-dir tmp_cleanup/spray-sheets] [--tray-size 3]

The default output directory ``tmp_cleanup/spray-sheets`` is gitignored. The
tool refuses to write inside a git repository unless git reports the directory
as ignored, so a facilitator-only file cannot be committed by accident.

Exit codes: 0 written; 2 the input or output location was rejected.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import secrets
import shutil
import subprocess  # nosec B404 - fixed git argv only, never a shell
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SHEET_VERSION = "facilitated-session-sheet v1.0"
DEFAULT_TRAY_SIZE = 3
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tmp_cleanup" / "spray-sheets"
REQUIRED_COLUMNS = ("session", "vial", "evaluator", "position", "blind_code")
_CODE = re.compile(r"^[A-Za-z0-9]{1,24}$")
_SLUG = re.compile(r"[^A-Za-z0-9]+")


class MappingError(ValueError):
    """The mapping file or the output location was rejected."""


@dataclass(frozen=True)
class TrayRow:
    """One tray position for one evaluator in one session."""

    session: str
    vial: str
    evaluator: str
    position: int
    blind_code: str
    persistent: bool
    paper_record_id: str


def _text(raw: dict[str, Any], key: str, line: int) -> str:
    """Return a stripped, non-empty text field or raise.

    Args:
        raw: One raw input record.
        key: The field name.
        line: A 1-based record number for the error message.

    Returns:
        The stripped value.

    Raises:
        MappingError: If the field is missing or blank.
    """
    value = str(raw.get(key) or "").strip()
    if not value:
        message = f"record {line}: '{key}' is required"
        raise MappingError(message)
    return value


def _records(path: Path) -> list[dict[str, Any]]:
    """Read raw records from a CSV or JSON mapping file.

    Args:
        path: The mapping file; ``.json`` is read as JSON, anything else as CSV.

    Returns:
        The raw records.

    Raises:
        MappingError: If the file is missing or not in the documented shape.
    """
    if not path.is_file():
        message = f"mapping file not found: {path}"
        raise MappingError(message)
    if path.suffix.lower() == ".json":
        data: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            message = "JSON mapping must be a list of objects"
            raise MappingError(message)
        return list(data)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            message = f"mapping is missing columns: {', '.join(missing)}"
            raise MappingError(message)
        return [dict(r) for r in reader]


def parse_mapping(path: Path) -> list[TrayRow]:
    """Parse a mapping file into validated tray rows.

    Args:
        path: The CSV or JSON mapping file.

    Returns:
        The tray rows in file order.

    Raises:
        MappingError: If a field is invalid or the same position or paper record ID
            is repeated.
    """
    rows: list[TrayRow] = []
    seen_ids: dict[tuple[str, str], str] = {}
    for line, raw in enumerate(_records(path), start=1):
        for column in REQUIRED_COLUMNS:
            _text(raw, column, line)
        code = _text(raw, "blind_code", line)
        if not _CODE.match(code):
            message = f"record {line}: blind_code must be 1-24 letters or digits"
            raise MappingError(message)
        try:
            position = int(_text(raw, "position", line))
        except ValueError:
            message = f"record {line}: position must be a whole number"
            raise MappingError(message) from None
        session = _text(raw, "session", line)
        evaluator = _text(raw, "evaluator", line)
        supplied = str(raw.get("paper_record_id") or "").strip()
        key = (session, evaluator)
        if supplied and seen_ids.setdefault(key, supplied) != supplied:
            message = f"record {line}: conflicting paper_record_id for {evaluator}"
            raise MappingError(message)
        rows.append(
            TrayRow(
                session=session,
                vial=_text(raw, "vial", line),
                evaluator=evaluator,
                position=position,
                blind_code=code,
                persistent=str(raw.get("persistent") or "").strip().lower()
                in {"yes", "y", "true", "1"},
                paper_record_id=supplied,
            )
        )
    return rows


def validate(rows: list[TrayRow], tray_size: int) -> None:
    """Check the shared-triple and uniqueness rules.

    Args:
        rows: Parsed tray rows.
        tray_size: Positions expected on every tray.

    Raises:
        MappingError: If the mapping is empty or breaks a rule.
    """
    if not rows:
        message = "mapping has no rows"
        raise MappingError(message)
    codes = [r.blind_code.upper() for r in rows]
    duplicates = sorted({c for c in codes if codes.count(c) > 1})
    if duplicates:
        message = f"blind codes must be unique, repeated: {', '.join(duplicates)}"
        raise MappingError(message)
    trays: dict[tuple[str, str], list[TrayRow]] = defaultdict(list)
    for row in rows:
        trays[(row.session, row.evaluator)].append(row)
    vial_sets: dict[str, set[frozenset[str]]] = defaultdict(set)
    for (session, evaluator), tray in trays.items():
        positions = sorted(r.position for r in tray)
        if positions != list(range(1, tray_size + 1)):
            message = (
                f"{evaluator} in session {session}: positions must be "
                f"1..{tray_size} exactly once, got {positions}"
            )
            raise MappingError(message)
        vials = [r.vial for r in tray]
        if len(set(vials)) != len(vials):
            message = f"{evaluator} in session {session}: a vial appears twice"
            raise MappingError(message)
        vial_sets[session].add(frozenset(vials))
    for session, sets in vial_sets.items():
        if len(sets) > 1:
            message = f"session {session}: evaluators do not share the same vials"
            raise MappingError(message)


def _slug(text: str) -> str:
    """Return a filename-safe form of a label.

    Args:
        text: Any label.

    Returns:
        The label with runs of other characters replaced by a hyphen.
    """
    return _SLUG.sub("-", text).strip("-") or "x"


def assign_record_ids(rows: list[TrayRow]) -> list[TrayRow]:
    """Give every evaluator-session a paper record ID, generating missing ones.

    Args:
        rows: Parsed tray rows.

    Returns:
        New rows with ``paper_record_id`` filled in and unique per tray.
    """
    chosen: dict[tuple[str, str], str] = {}
    for row in rows:
        if row.paper_record_id:
            chosen.setdefault((row.session, row.evaluator), row.paper_record_id)
    used = set(chosen.values())
    for row in rows:
        key = (row.session, row.evaluator)
        if key not in chosen:
            candidate = f"PR-{secrets.token_hex(3).upper()}"
            while candidate in used:
                candidate = f"PR-{secrets.token_hex(3).upper()}"
            used.add(candidate)
            chosen[key] = candidate
    return [
        TrayRow(
            r.session,
            r.vial,
            r.evaluator,
            r.position,
            r.blind_code,
            r.persistent,
            chosen[(r.session, r.evaluator)],
        )
        for r in rows
    ]


def evaluator_header(
    evaluator: str,
    record_id: str,
    tray: list[TrayRow],
    sheet_version: str,
) -> str:
    """Render the evaluator-facing header for one tray.

    It carries only the sheet version, the paper record ID, the evaluator
    reference and the blind codes in tray order: no vial, session key or identity.

    Args:
        evaluator: The opaque evaluator reference.
        record_id: The paper record ID.
        tray: The evaluator's tray rows for the session.
        sheet_version: The printed sheet version id.

    Returns:
        Markdown text for printing.
    """
    ordered = sorted(tray, key=lambda r: r.position)
    codes = " | ".join(r.blind_code for r in ordered)
    return (
        f"Sheet version: {sheet_version}\n\n"
        "| Field | Entry |\n| --- | --- |\n"
        f"| Paper record ID | {record_id} |\n"
        f"| Assigned evaluator reference | {evaluator} |\n\n"
        "| Row | Sample 1 | Sample 2 | Sample 3 |\n| --- | --- | --- | --- |\n"
        f"| Blind code (pre-printed) | {codes} |\n"
    )


def spray_sheet(session: str, tray_size: int, rows: list[TrayRow]) -> str:
    """Render the facilitator-only spray sheet for one session.

    Args:
        session: The facilitator's session key.
        tray_size: Positions per tray.
        rows: Every tray row in that session.

    Returns:
        Markdown text. It contains vial numbers and is facilitator-only.
    """
    lines = [
        f"# Spray sheet, session {session}",
        "",
        "FACILITATOR ONLY. Contains vial numbers. Never show, commit or email.",
        "",
        "Spray one round at a time (one blotter per evaluator). Write the sprayed time",
        "on each evaluator's sheet. Provisional ceiling from spray to first smell: 5 minutes.",
        "",
    ]
    for position in range(1, tray_size + 1):
        lines += [
            f"## Round {position}: tray position {position}",
            "",
            "| Vial | Evaluator | Blind code | Persistent | Sprayed (hh:mm:ss) |",
            "| --- | --- | --- | --- | --- |",
        ]
        in_round = sorted(
            (r for r in rows if r.position == position),
            key=lambda r: (r.vial, r.evaluator),
        )
        lines += [
            f"| {r.vial} | {r.evaluator} | {r.blind_code} | "
            f"{'extend clean air to about 5 min' if r.persistent else ''} | |"
            for r in in_round
        ]
        lines.append("")
    lines += ["## Trays by evaluator", ""]
    by_eval: dict[str, list[TrayRow]] = defaultdict(list)
    for row in rows:
        by_eval[row.evaluator].append(row)
    for evaluator in sorted(by_eval):
        tray = sorted(by_eval[evaluator], key=lambda r: r.position)
        cells = "; ".join(f"{r.position}: {r.blind_code} (vial {r.vial})" for r in tray)
        lines.append(f"- {evaluator} ({tray[0].paper_record_id}): {cells}")
    lines.append("")
    return "\n".join(lines)


def refuse_unignored_repo_path(directory: Path) -> None:
    """Refuse an output directory inside a git repository that does not ignore it.

    A directory outside any repository is allowed.

    Args:
        directory: The intended output directory (it need not exist yet).

    Raises:
        MappingError: If the directory is in a repository and not git-ignored.
    """
    git = shutil.which("git")
    if git is None:
        # Without git nothing here can be committed through it.
        return
    existing = directory
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    top = subprocess.run(  # nosec B603 - fixed argv, no shell
        [git, "-C", str(existing), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if top.returncode != 0:
        return
    probe = directory / "probe.md"
    ignored = subprocess.run(  # nosec B603 - fixed argv, no shell
        [git, "-C", top.stdout.strip(), "check-ignore", "-q", str(probe)],
        capture_output=True,
        check=False,
    )
    if ignored.returncode != 0:
        message = (
            f"refusing to write facilitator-only output to {directory}: "
            "it is inside a git repository and is not git-ignored"
        )
        raise MappingError(message)


def write_outputs(
    rows: list[TrayRow],
    output_dir: Path,
    tray_size: int,
    sheet_version: str,
) -> list[Path]:
    """Write every output file.

    Args:
        rows: Validated rows with paper record IDs assigned.
        output_dir: Where to write; must be ignored if inside a repository.
        tray_size: Positions per tray.
        sheet_version: The printed sheet version id.

    Returns:
        The files written.
    """
    refuse_unignored_repo_path(output_dir)
    facilitator = output_dir / "facilitator-only"
    evaluators = output_dir / "evaluator-headers"
    facilitator.mkdir(parents=True, exist_ok=True)
    evaluators.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    by_session: dict[str, list[TrayRow]] = defaultdict(list)
    trays: dict[tuple[str, str], list[TrayRow]] = defaultdict(list)
    for row in rows:
        by_session[row.session].append(row)
        trays[(row.session, row.evaluator)].append(row)
    for session, session_rows in by_session.items():
        sheet = facilitator / f"spray-sheet-session-{_slug(session)}.md"
        sheet.write_text(
            spray_sheet(session, tray_size, session_rows), encoding="utf-8"
        )
        written.append(sheet)
    index = facilitator / "paper-record-index.csv"
    with index.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["paper_record_id", "session", "evaluator"])
        for (session, evaluator), tray in sorted(trays.items()):
            writer.writerow([tray[0].paper_record_id, session, evaluator])
    written.append(index)
    for (_session, evaluator), tray in sorted(trays.items()):
        # The filename is the random paper record ID only: no session key,
        # because a session key can reveal a holdout or repeat position.
        name = f"{_slug(tray[0].paper_record_id)}-{_slug(evaluator)}.md"
        header = evaluators / name
        header.write_text(
            evaluator_header(evaluator, tray[0].paper_record_id, tray, sheet_version),
            encoding="utf-8",
        )
        written.append(header)
    return written


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n", maxsplit=1)[0]
    )
    parser.add_argument(
        "--mapping", type=Path, required=True, help="CSV or JSON mapping"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="output directory (default: gitignored tmp_cleanup/spray-sheets)",
    )
    parser.add_argument("--tray-size", type=int, default=DEFAULT_TRAY_SIZE)
    parser.add_argument("--sheet-version", default=SHEET_VERSION)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the tool.

    Args:
        argv: Arguments, defaulting to ``sys.argv``.

    Returns:
        The exit code: 0 on success, 2 if the input or output was rejected.
    """
    args = build_parser().parse_args(argv)
    try:
        rows = parse_mapping(args.mapping)
        validate(rows, args.tray_size)
        written = write_outputs(
            assign_record_ids(rows), args.output_dir, args.tray_size, args.sheet_version
        )
    except MappingError as error:
        sys.stderr.write(f"error: {error}\n")
        return 2
    sys.stdout.write(f"wrote {len(written)} files under {args.output_dir}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
