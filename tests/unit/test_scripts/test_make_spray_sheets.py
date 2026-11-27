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
HEADER = [
    "session",
    "vial",
    "evaluator",
    "position",
    "blind_code",
    "persistent",
    "atomizer",
]
VIALS = {"A": ["V01", "V02", "V03"], "B": ["V04", "V05", "V06"]}
ATOMIZERS = {
    "V01": "B07",
    "V02": "B21",
    "V03": "H03",
    "V04": "B12",
    "V05": "B33",
    "V06": "H09",
}
ATOMIZER_COLUMN = HEADER.index("atomizer")
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
                        ATOMIZERS[vial],
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
        assert "facilitated-session-sheet v2.2" in text
        assert "Individual trays" in text
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
            "atomizer": f"B0{n}",
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


def group_rows() -> list[list[str]]:
    """Build a two-session mapping where every evaluator shares codes and order."""
    rows: list[list[str]] = []
    counter = 0
    for session, vials in VIALS.items():
        codes = {}
        for vial in vials:
            counter += 1
            codes[vial] = f"GG{counter:04d}"
        for evaluator in EVALUATORS:
            for position, vial in enumerate(vials, start=1):
                persistent = "yes" if vial == "V02" else ""
                rows.append(
                    [
                        session,
                        vial,
                        evaluator,
                        str(position),
                        codes[vial],
                        persistent,
                        ATOMIZERS[vial],
                    ]
                )
    return rows


def test_group_mode_accepts_shared_codes_and_order(tmp_path: Path) -> None:
    """Group mode prints the same codes on every header and one blotter per sample."""
    rows = group_rows()
    mapping = write_csv(tmp_path / "mapping.csv", rows)
    out = tmp_path / "out"
    args = ["--mapping", str(mapping), "--output-dir", str(out), "--mode", "group"]
    assert tool.main(args) == 0

    headers = sorted((out / "evaluator-headers").glob("*.md"))
    assert len(headers) == 6
    forbidden = [
        *(v for vials in VIALS.values() for v in vials),
        "persistent",
        "extend",
    ]
    texts = [h.read_text(encoding="utf-8") for h in headers]
    for text, header in zip(texts, headers, strict=True):
        assert "facilitated-session-sheet v2.2" in text
        assert "Group blotter" in text
        for token in forbidden:
            assert token not in text
        assert "session" not in header.name.lower()
    session_a_codes = [r[4] for r in rows if r[0] == "A" and r[2] == "E1"]
    line = f"| Blind code (pre-printed) | {' | '.join(session_a_codes)} |"
    assert sum(line in text for text in texts) == len(EVALUATORS)

    sheet = (out / "facilitator-only" / "spray-sheet-session-A.md").read_text(
        encoding="utf-8"
    )
    assert "FACILITATOR ONLY" in sheet
    assert "ONE blotter per sample" in sheet
    assert "## Seat order" in sheet
    assert "| 1 | E1 |" in sheet
    assert "## Sample 1: vial V01" in sheet
    assert "## Sample 2: vial V02" in sheet
    assert "extend clean air to about 5 min" in sheet
    assert "Replacement 1" in sheet
    assert "spray + 2:00" in sheet
    assert "DIFFERENT number" in sheet
    assert "5 minutes from" not in sheet


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda rows: rows[0].__setitem__(4, "DIFF01"), "one blind code"),
        (
            lambda rows: [
                r.__setitem__(4, "GG0001") for r in rows if r[:2] == ["A", "V02"]
            ],
            "unique per vial",
        ),
        (
            lambda rows: (
                rows[0].__setitem__(1, "V02"),
                rows[0].__setitem__(4, rows[1][4]),
                rows[1].__setitem__(1, "V01"),
                rows[1].__setitem__(4, "GG0001"),
            ),
            "same vial for every evaluator",
        ),
    ],
)
def test_group_mode_rejects_differing_codes_or_order(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mutate: object,
    fragment: str,
) -> None:
    """Group mode requires one code per vial, one order and no code shared by vials."""
    rows = group_rows()
    assert callable(mutate)
    mutate(rows)
    mapping = write_csv(tmp_path / "mapping.csv", rows)
    out = tmp_path / "out"
    args = ["--mapping", str(mapping), "--output-dir", str(out), "--mode", "group"]
    assert tool.main(args) == 2
    assert fragment in capsys.readouterr().err
    assert not out.exists()


def test_individual_mode_still_rejects_shared_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Shared codes are valid only in group mode; the default stays strict."""
    mapping = write_csv(tmp_path / "mapping.csv", group_rows())
    out = tmp_path / "out"
    assert tool.main(["--mapping", str(mapping), "--output-dir", str(out)]) == 2
    assert "unique" in capsys.readouterr().err
    assert not out.exists()


def test_group_mode_output_is_still_refused_in_an_unignored_repository(
    tmp_path: Path,
) -> None:
    """Group mode keeps the git-ignore guard on facilitator-only output."""
    subprocess.run(  # noqa: S603 - fixed argv, test-only
        ["git", "init", "-q", str(tmp_path / "repo")],  # noqa: S607
        check=True,
    )
    mapping = write_csv(tmp_path / "mapping.csv", group_rows())
    out = tmp_path / "repo" / "private-out"
    args = ["--mapping", str(mapping), "--output-dir", str(out), "--mode", "group"]
    assert tool.main(args) == 2
    assert not (out / "facilitator-only").exists()


def test_unknown_mode_is_rejected(tmp_path: Path) -> None:
    """validate() rejects a mode that is not individual or group."""
    rows = tool.parse_mapping(write_csv(tmp_path / "m.csv", synthetic_rows()))
    with pytest.raises(tool.MappingError, match="unknown mode"):
        tool.validate(rows, 3, "pair")


def test_individual_spray_sheet_states_both_numbers(tmp_path: Path) -> None:
    """The individual sheet names the 2 minute ceiling and the separate clean-air interval."""
    mapping = write_csv(tmp_path / "mapping.csv", synthetic_rows())
    out = tmp_path / "out"
    assert tool.main(["--mapping", str(mapping), "--output-dir", str(out)]) == 0
    text = (out / "facilitator-only" / "spray-sheet-session-A.md").read_text(
        encoding="utf-8"
    )
    assert "2 minutes (provisional)" in text
    assert "different number" in text
    assert "5 minutes" not in text.split("different number")[0]


def _run(tmp_path: Path, rows: list[list[str]], mode: str) -> tuple[int, Path]:
    """Write a mapping, run the tool in the given mode and return code and output."""
    mapping = write_csv(tmp_path / "mapping.csv", rows)
    out = tmp_path / "out"
    args = ["--mapping", str(mapping), "--output-dir", str(out), "--mode", mode]
    return tool.main(args), out


def _rows_for(mode: str) -> list[list[str]]:
    """Return the synthetic mapping for the given mode."""
    return group_rows() if mode == "group" else synthetic_rows()


def _header_for(out: Path, rows: list[list[str]], session: str, evaluator: str) -> str:
    """Return the evaluator header text for one session and evaluator."""
    index = list(
        csv.DictReader(
            (out / "facilitator-only" / "paper-record-index.csv").open(encoding="utf-8")
        )
    )
    record = next(
        r for r in index if r["session"] == session and r["evaluator"] == evaluator
    )
    file = next((out / "evaluator-headers").glob(f"{record['paper_record_id']}-*.md"))
    assert rows
    return file.read_text(encoding="utf-8")


@pytest.mark.parametrize("mode", ["individual", "group"])
def test_header_prints_atomizer_row_in_tray_order_without_vials(
    tmp_path: Path, mode: str
) -> None:
    """The atomizer row sits under the code row, in tray order, with no vial value."""
    rows = _rows_for(mode)
    status, out = _run(tmp_path, rows, mode)
    assert status == 0
    mine = [r for r in rows if r[0] == "A" and r[2] == "E2"]
    codes = " | ".join(r[4] for r in mine)
    atomizers = " | ".join(r[ATOMIZER_COLUMN] for r in mine)
    text = _header_for(out, rows, "A", "E2")
    assert (
        f"| Blind code (pre-printed) | {codes} |\n| Atomizer | {atomizers} |\n" in text
    )
    for vials in VIALS.values():
        for vial in vials:
            assert vial not in text
    assert "persistent" not in text
    assert "extend" not in text


@pytest.mark.parametrize("mode", ["individual", "group"])
def test_spray_sheet_shows_the_atomizer_next_to_the_vial(
    tmp_path: Path, mode: str
) -> None:
    """The facilitator-only sheet carries the atomizer beside each vial."""
    status, out = _run(tmp_path, _rows_for(mode), mode)
    assert status == 0
    text = (out / "facilitator-only" / "spray-sheet-session-A.md").read_text(
        encoding="utf-8"
    )
    assert "(vial V01, atomizer B07)" in text
    if mode == "group":
        assert "## Sample 1: vial V01, atomizer B07, blind code" in text
    else:
        assert "| Vial | Atomizer | Evaluator |" in text
        assert "| V01 | B07 | E1 |" in text


@pytest.mark.parametrize("mode", ["individual", "group"])
def test_missing_atomizer_column_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: str
) -> None:
    """A CSV without the atomizer column, or with a blank value, is rejected."""
    rows = [r[:ATOMIZER_COLUMN] for r in _rows_for(mode)]
    mapping = tmp_path / "mapping.csv"
    with mapping.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER[:ATOMIZER_COLUMN])
        writer.writerows(rows)
    out = tmp_path / "out"
    args = ["--mapping", str(mapping), "--output-dir", str(out), "--mode", mode]
    assert tool.main(args) == 2
    assert "atomizer" in capsys.readouterr().err
    assert not out.exists()

    blank = _rows_for(mode)
    blank[0][ATOMIZER_COLUMN] = " "
    status, out = _run(tmp_path, blank, mode)
    assert status == 2
    assert "'atomizer' is required" in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize("mode", ["individual", "group"])
def test_atomizer_reused_across_two_vials_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: str
) -> None:
    """One atomizer may not serve two different vials."""
    rows = _rows_for(mode)
    for row in rows:
        if row[1] == "V02":
            row[ATOMIZER_COLUMN] = ATOMIZERS["V01"]
    status, out = _run(tmp_path, rows, mode)
    assert status == 2
    err = capsys.readouterr().err
    assert "atomizer B07 is used for more than one vial" in err
    assert "V01, V02" in err
    assert not out.exists()


@pytest.mark.parametrize("mode", ["individual", "group"])
def test_one_vial_with_two_atomizers_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: str
) -> None:
    """One vial may not appear under two different atomizers."""
    rows = _rows_for(mode)
    rows[0][ATOMIZER_COLUMN] = "B99"
    status, out = _run(tmp_path, rows, mode)
    assert status == 2
    err = capsys.readouterr().err
    assert f"vial {rows[0][1]} has more than one atomizer" in err
    assert "B99" in err
    assert not out.exists()


def test_atomizer_with_a_table_separator_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An atomizer label that would break the printed table is rejected."""
    rows = synthetic_rows()
    rows[0][ATOMIZER_COLUMN] = "B|07"
    status, out = _run(tmp_path, rows, "individual")
    assert status == 2
    assert "atomizer must not contain" in capsys.readouterr().err
    assert not out.exists()
