"""Tests for ``scripts/make_spray_sheets.py`` using synthetic mappings only."""

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).parents[3]
HEADER = ["session", "vial", "evaluator", "position", "blind_code", "persistent"]
VIALS = {"A": ["V01", "V02", "V03"], "B": ["V04", "V05", "V06"]}
EVALUATORS = ["E1", "E2", "E3"]


def load_script() -> ModuleType:
    """Load the spray-sheet script as a module."""
    path = ROOT / "scripts" / "make_spray_sheets.py"
    spec = importlib.util.spec_from_file_location("make_spray_sheets", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = load_script()


def synthetic_rows() -> list[list[str]]:
    """Build a rotated two-session, three-evaluator mapping with fake codes."""
    rows: list[list[str]] = []
    counter = 0
    for session, vials in VIALS.items():
        for shift, evaluator in enumerate(EVALUATORS):
            for position in range(1, 4):
                counter += 1
                vial = vials[(position - 1 + shift) % 3]
                persistent = "yes" if vial == "V02" else ""
                rows.append(
                    [
                        session,
                        vial,
                        evaluator,
                        str(position),
                        f"ZZ{counter:04d}",
                        persistent,
                    ]
                )
    return rows


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    """Write a mapping CSV."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return path


def test_outputs_are_written_and_evaluator_files_leak_nothing(tmp_path: Path) -> None:
    """Evaluator files carry codes only; no vial, session key or persistent hint."""
    mapping = write_csv(tmp_path / "mapping.csv", synthetic_rows())
    out = tmp_path / "out"
    assert tool.main(["--mapping", str(mapping), "--output-dir", str(out)]) == 0

    headers = sorted((out / "evaluator-headers").glob("*.md"))
    assert len(headers) == 6
    forbidden = [
        *(v for vials in VIALS.values() for v in vials),
        "persistent",
        "extend",
    ]
    for header in headers:
        text = header.read_text(encoding="utf-8")
        assert "facilitated-session-sheet v1.0" in text
        assert "Blind code (pre-printed)" in text
        for token in forbidden:
            assert token not in text
        # File names must not carry the session key either.
        assert "session" not in header.name.lower()
        assert not header.name.lower().startswith(("a-", "b-"))

    sheets = sorted((out / "facilitator-only").glob("spray-sheet-session-*.md"))
    assert [s.name for s in sheets] == [
        "spray-sheet-session-A.md",
        "spray-sheet-session-B.md",
    ]
    text = sheets[0].read_text(encoding="utf-8")
    assert "FACILITATOR ONLY" in text
    assert "V01" in text
    assert "extend clean air to about 5 min" in text


def test_header_codes_follow_tray_position_order(tmp_path: Path) -> None:
    """The printed header lists the three codes in the evaluator's own order."""
    rows = synthetic_rows()
    mapping = write_csv(tmp_path / "mapping.csv", rows)
    out = tmp_path / "out"
    assert tool.main(["--mapping", str(mapping), "--output-dir", str(out)]) == 0
    index = list(
        csv.DictReader(
            (out / "facilitator-only" / "paper-record-index.csv").open(encoding="utf-8")
        )
    )
    assert len(index) == 6
    record = next(r for r in index if r["session"] == "A" and r["evaluator"] == "E2")
    file = next((out / "evaluator-headers").glob(f"{record['paper_record_id']}-*.md"))
    expected = [r[4] for r in rows if r[0] == "A" and r[2] == "E2"]
    assert f"| {' | '.join(expected)} |" in file.read_text(encoding="utf-8")
    ids = {r["paper_record_id"] for r in index}
    assert len(ids) == 6
    assert all(i.startswith("PR-") for i in ids)


def test_json_input_and_supplied_record_ids(tmp_path: Path) -> None:
    """JSON mappings work and a supplied paper record ID is kept."""
    records = [
        {
            "session": "A",
            "vial": f"V{n}",
            "evaluator": "E1",
            "position": n,
            "blind_code": f"QQ{n}",
            "paper_record_id": "PR-FIXED1",
        }
        for n in (1, 2, 3)
    ]
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps(records), encoding="utf-8")
    out = tmp_path / "out"
    assert tool.main(["--mapping", str(mapping), "--output-dir", str(out)]) == 0
    assert (out / "evaluator-headers" / "PR-FIXED1-E1.md").is_file()


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda rows: rows[1].__setitem__(4, rows[0][4]), "unique"),
        (lambda rows: rows.pop(0), "positions must be"),
        (lambda rows: rows[0].__setitem__(3, "9"), "positions must be"),
        (lambda rows: rows[0].__setitem__(4, "bad code!"), "letters or digits"),
        (lambda rows: rows[0].__setitem__(1, ""), "'vial' is required"),
        (lambda rows: rows[0].__setitem__(3, "one"), "whole number"),
        (lambda rows: rows[0].__setitem__(1, "V99"), "do not share the same vials"),
    ],
)
def test_invalid_mappings_are_rejected(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mutate: object,
    fragment: str,
) -> None:
    """Every documented rule is enforced and nothing is written on failure."""
    rows = synthetic_rows()
    assert callable(mutate)
    mutate(rows)
    mapping = write_csv(tmp_path / "mapping.csv", rows)
    out = tmp_path / "out"
    assert tool.main(["--mapping", str(mapping), "--output-dir", str(out)]) == 2
    assert fragment in capsys.readouterr().err
    assert not out.exists()


def test_missing_file_and_missing_columns(tmp_path: Path) -> None:
    """A missing file or a header without a required column is rejected."""
    assert tool.main(["--mapping", str(tmp_path / "nope.csv")]) == 2
    bad = tmp_path / "bad.csv"
    bad.write_text("session,vial\nA,V1\n", encoding="utf-8")
    assert tool.main(["--mapping", str(bad), "--output-dir", str(tmp_path / "o")]) == 2


def test_default_output_directory_is_gitignored() -> None:
    """The default facilitator-only location is covered by the repo .gitignore."""
    probe = tool.DEFAULT_OUTPUT_DIR / "facilitator-only" / "spray-sheet-session-A.md"
    result = subprocess.run(  # noqa: S603 - fixed argv, test-only
        ["git", "-C", str(ROOT), "check-ignore", "-q", str(probe)],  # noqa: S607
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0


def test_refuses_unignored_directory_inside_a_repository(tmp_path: Path) -> None:
    """Output inside a repository is refused unless git ignores it."""
    subprocess.run(  # noqa: S603 - fixed argv, test-only
        ["git", "init", "-q", str(tmp_path / "repo")],  # noqa: S607
        check=True,
    )
    repo = tmp_path / "repo"
    mapping = write_csv(tmp_path / "mapping.csv", synthetic_rows())
    out = repo / "private-out"
    assert tool.main(["--mapping", str(mapping), "--output-dir", str(out)]) == 2
    assert not (out / "facilitator-only").exists()

    (repo / ".gitignore").write_text("private-out/\n", encoding="utf-8")
    assert tool.main(["--mapping", str(mapping), "--output-dir", str(out)]) == 0
    assert (out / "facilitator-only" / "paper-record-index.csv").is_file()
