"""Tests for the generic two-sided session sheet renderer and its source doc."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).parents[3]
SHEET_DOC = ROOT / "docs" / "facilitated-session-sheet.md"
FORMS_CSS = ROOT / "scripts" / "print" / "forms.css"
VERSION = "facilitated-session-sheet v3.0"
MIN_FONT_PT = 8.0

# Every field label the v3.0 spec requires, front then back.
REQUIRED_FRONT = [
    "Blotter mode",
    "Individual trays",
    "Local date",
    "Time zone",
    "Recorder initials",
    "Sample 1",
    "Sample 2",
    "Sample 3",
    "Time sprayed",
    "Time first smelled",
    "Time this column finished",
    "Do you recognize this?",
    "Have you owned or worn it?",
    "What you perceived",
    "Intensity",
    "Sweetness",
    "Freshness",
    "Density",
    "Dryness",
    "Clean or soapy",
    "Earthy or rooty",
    "Bodily or animalic",
    "How you responded",
    "Liking",
    "Discomfort",
    "Would wear",
    "Would buy",
    "How sure you are",
    "Confidence",
    "Familiarity",
    "Column complete",
    "Evaluator initials",
    "Evaluator reference",
    "Paper record ID",
]
REQUIRED_BACK = [
    "Type of event",
    "Work or school",
    "At home",
    "Social outing",
    "Formal event",
    "Outdoor activity",
    "Something else",
    "Season",
    "Spring",
    "Summer",
    "Fall",
    "Winter",
    "Year-round",
    "None of these",
    "Cannot judge",
    "Perceived notes",
    "What you liked",
    "What you disliked",
    "Reminds you of",
    "Anything else",
    "I would rather not rank",
    "I could not tell them apart",
    "Session start time",
    "Session end time",
    "Ranking time",
]
REMOVED = [
    "Detected row",
    "Not answering because",
    "Consent on file",
    "Data classification",
]
# The skip-reason boxes are gone from the printed form; the doc still names these
# values because the transcriber chooses among them from the margin note.
REMOVED_FROM_FORM_ONLY = ["Skipped", "Unable", "Interrupted"]


def load_script() -> ModuleType:
    """Load the sheet renderer as a module."""
    path = ROOT / "scripts" / "render_session_sheet.py"
    spec = importlib.util.spec_from_file_location("render_session_sheet", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = load_script()


def _text(html: str) -> str:
    """Strip tags so labels can be matched as printed words."""
    return re.sub(r"<[^>]+>", " ", html)


def test_front_carries_every_required_field_label() -> None:
    """The printed front names every required field."""
    text = _text(tool.front(VERSION))
    for label in REQUIRED_FRONT:
        assert label in text, label


def test_back_carries_every_required_field_label() -> None:
    """The printed back names every required field."""
    text = _text(tool.back(VERSION))
    for label in REQUIRED_BACK:
        assert label in text, label


@pytest.mark.parametrize("label", REQUIRED_FRONT + REQUIRED_BACK)
def test_source_doc_names_every_required_field_label(label: str) -> None:
    """The source document lists each field the form prints."""
    assert label in SHEET_DOC.read_text(encoding="utf-8")


@pytest.mark.parametrize("label", REMOVED)
def test_removed_fields_are_gone_from_form_and_doc(label: str) -> None:
    """None of the removed v2.2 fields is printed or listed."""
    html = tool.render_html(VERSION).lower()
    doc = SHEET_DOC.read_text(encoding="utf-8").lower()
    assert label.lower() not in _text(html)
    assert label.lower() not in doc


@pytest.mark.parametrize("label", REMOVED_FROM_FORM_ONLY)
def test_skip_reason_boxes_are_gone_from_the_form(label: str) -> None:
    """No skip-reason tick box is printed."""
    assert label.lower() not in _text(tool.render_html(VERSION)).lower()


def test_recognize_row_reads_no_vaguely_exactly() -> None:
    """The Recognize row uses No / Vaguely / Exactly, never New."""
    html = tool.front(VERSION)
    row = html.split("Do you recognize this?")[1].split("Have you owned")[0]
    for word in ("No", "Vaguely", "Exactly"):
        assert f"<i>{word}</i>" in row
    assert "New" not in row


def test_intensity_anchor_says_not_detected() -> None:
    """Intensity 0 is printed as not detected."""
    html = tool.front(VERSION)
    assert "0 not detected," in html
    assert "5 overpowering" in html


def test_identity_is_written_in_and_both_session_numbers_blank() -> None:
    """Nothing per evaluator is pre-printed: both session numbers are write-ins."""
    html = tool.render_html(VERSION)
    assert html.count("Session ___ of ___, evaluator ___") == 2
    assert "of 17" not in html
    assert "side 1 of 2" in html
    assert "side 2 of 2" in html
    assert html.count(VERSION) >= 3  # title and both footers
    assert html.count('class="sheet front"') == 1
    assert html.count('class="sheet back"') == 1


def test_only_individual_trays_is_preticked() -> None:
    """Exactly one box on the whole sheet is pre-ticked."""
    html = tool.render_html(VERSION)
    assert html.count('class="bx on"') == 1
    assert "<b>Individual trays</b>" in html


def test_css_never_prints_text_below_eight_points() -> None:
    """Every font-size in the sheet stylesheet is at least 8 pt."""
    sizes = [
        float(m) for m in re.findall(r"font-size:\s*([0-9.]+)pt", FORMS_CSS.read_text())
    ]
    assert sizes
    assert min(sizes) >= MIN_FONT_PT


def test_main_writes_the_html_file(tmp_path: Path) -> None:
    """The CLI entry writes a standalone HTML document."""
    out = tmp_path / "sheet.html"
    assert tool.main([str(out), "--version", VERSION]) == 0
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")
