"""Render the generic two-sided facilitated session sheet (v3.0) as HTML.

The sheet is ONE generic master form printed double-sided on one US Letter sheet
(flip on the long edge) for any session and any evaluator. Nothing per session or
per evaluator is pre-printed: the session numbers, evaluator reference, paper
record ID and the three sample codes (the code written on the atomizer) are all
handwritten. Only the blotter mode is pre-ticked (Individual trays).

This module only builds HTML. ``scripts/print_forms.sh`` prints it to a PDF with
Chrome and asserts the page count (2). The CSS lives in ``scripts/print/forms.css``.
The field wording here mirrors ``docs/facilitated-session-sheet.md``; a unit test
checks both for the required field labels.

Usage:
    python scripts/render_session_sheet.py OUTPUT.html \\
        --version "facilitated-session-sheet v3.0"
"""

from __future__ import annotations

import argparse
import sys
from html import escape
from pathlib import Path

CSS_PATH = Path(__file__).resolve().parent / "print" / "forms.css"

PERCEIVED_ROWS: tuple[tuple[str, str, str], ...] = (
    ("Intensity", "not detected", "overpowering"),
    ("Sweetness", "not sweet", "very sweet"),
    ("Freshness", "not fresh", "very fresh"),
    ("Density", "thin and airy", "thick and heavy"),
    ("Dryness", "not dry", "very dry"),
    ("Clean or soapy", "not at all", "strongly"),
    ("Earthy or rooty", "not at all", "strongly"),
    ("Bodily or animalic", "not at all", "strongly"),
)
RESPONSE_ROWS: tuple[tuple[str, str, str, int], ...] = (
    ("Liking", "strongly dislike", "love it", 10),
    ("Discomfort", "comfortable", "had to step away", 5),
    ("Would wear", "never", "definitely", 10),
    ("Would buy", "never", "definitely", 10),
)
SURE_ROWS: tuple[tuple[str, str, str, int], ...] = (
    ("Confidence", "just guessing", "completely sure", 5),
    ("Familiarity", "completely new to me", "I know this well", 5),
)
EVENT_CHOICES = (
    "Work or school",
    "At home",
    "Social outing",
    "Formal event",
    "Outdoor activity",
    "Something else",
)
SEASON_CHOICES = ("Spring", "Summer", "Fall", "Winter", "Year-round")
NOTE_ROWS: tuple[tuple[str, str, bool], ...] = (
    ("Perceived notes", "separate with commas", True),
    ("What you liked", "", False),
    ("What you disliked", "", False),
    ("Reminds you of", "", False),
    ("Anything else", "", False),
)
SAMPLES = 3
WRITE_AREA = '<div class="wrbox"></div>'


def _box(*, ticked: bool = False) -> str:
    """Return an empty (or pre-ticked) check box."""
    return f'<span class="bx{" on" if ticked else ""}"></span>'


def _write_box(style: str = "") -> str:
    """Return a handwriting box."""
    attr = f' style="{style}"' if style else ""
    return f'<span class="wbox"{attr}></span>'


def _cells(inner: str) -> str:
    """Repeat one cell body across the three sample columns."""
    return "".join(f'<div class="c">{inner}</div>' for _ in range(SAMPLES))


def _digits(top: int) -> str:
    """Return the circle-one digits 0..top."""
    cls = "s5" if top == 5 else "s10"
    body = "".join(f"<i>{k}</i>" for k in range(top + 1))
    return f'<div class="dg {cls}">{body}</div>'


def _options(*names: str) -> str:
    """Return a circle-one word choice."""
    return '<div class="opt">' + "".join(f"<i>{n}</i>" for n in names) + "</div>"


def _label(name: str, sub: str = "") -> str:
    """Return a row label with an optional small sub line."""
    sub_html = f'<span class="sub">{escape(sub)}</span>' if sub else ""
    return f'<div class="lab"><span class="nm">{escape(name)}</span>{sub_html}</div>'


def _scale_row(name: str, low: str, high: str, top: int) -> str:
    """Return one anchored 0..top scale row."""
    small = " sm2" if len(name) > 16 else ""
    label = (
        f'<div class="lab"><div class="nm{small}">{escape(name)}</div>'
        f'<div class="an"><span>0 {escape(low)},</span>'
        f"<span>{top} {escape(high)}</span></div></div>"
    )
    return f'<div class="row">{label}{_cells(_digits(top))}</div>'


def _time_row(name: str, sub: str = "") -> str:
    """Return a hh:mm:ss write-in row."""
    body = '<div class="tm"><span>hh:mm:ss</span><b class="wr3"></b></div>'
    return (
        f'<div class="row" style="min-height:23pt">{_label(name, sub)}'
        f"{_cells(body)}</div>"
    )


def _simple_row(name: str, inner: str) -> str:
    """Return a one-line answer row."""
    return (
        f'<div class="row" style="min-height:27pt">{_label(name)}{_cells(inner)}</div>'
    )


def _group(title: str, desc: str) -> str:
    """Return a shaded group heading."""
    return f'<div class="grp"><b>{escape(title)}</b><span>{escape(desc)}</span></div>'


def _foot(side: int, version: str) -> str:
    """Return the footer: both session numbers and the evaluator are write-ins."""
    return (
        '<div class="foot">'
        f"<span>Session ___ of ___, evaluator ___ | side {side} of 2</span>"
        f"<span><b>{escape(version)}</b></span></div>"
    )


def _title_bar(title: str) -> str:
    """Return the black title bar with the handwritten identity boxes."""
    return (
        f'<div class="titlebar"><span class="t">{title}</span>'
        '<span class="s2"><small>Session</small>'
        f'{_write_box("width:0.5in")}<small style="margin-left:3pt">of</small>'
        f"{_write_box('width:0.5in')}</span>"
        '<span class="s2"><small>Evaluator reference</small>'
        f"{_write_box('width:0.6in')}</span>"
        '<span class="s2"><small>Paper record ID</small>'
        f"{_write_box('width:1.25in')}</span></div>"
    )


def _codes_band(title: str, sub: str, *, small: bool = False) -> str:
    """Return the black band with the three handwritten sample code boxes."""
    heads = "".join(
        f'<span class="hc"><small>Sample {i}<br>code</small>{_write_box()}</span>'
        for i in range(1, SAMPLES + 1)
    )
    sub_html = f"<small>{escape(sub)}</small>" if sub else ""
    cls = " small" if small else ""
    return (
        f'<div class="band tall{cls}"><span class="t2"><b>{escape(title)}</b>'
        f"{sub_html}</span>{heads}</div>"
    )


def _tick_grid(
    first: tuple[str, ...],
    extras: tuple[tuple[str, bool], ...],
    cls: str = "",
) -> str:
    """Return a two-column tick grid followed by full-width lines."""
    short = "".join(f'<span class="tk">{_box()}{escape(e)}</span>' for e in first)
    full = "".join(
        f'<span class="tk full">{_box()}{escape(name)}'
        f"{'<em>tick only this</em>' if only else ''}</span>"
        for name, only in extras
    )
    return f'<div class="ev{cls}">{short}{full}</div>'


def _event_rows() -> str:
    """Return the Type of event and Season rows (back side)."""
    event = _label(
        "Type of event", "where would you wear it? tick all that fit"
    ) + _cells(
        _tick_grid(
            EVENT_CHOICES,
            (("None of these", True), ("Cannot judge", True)),
            " tight",
        )
    )
    season = _label("Season", "when would you wear it? tick all that fit") + _cells(
        _tick_grid(
            SEASON_CHOICES,
            (
                ("None of these", True),
                ("Cannot judge", True),
            ),
        )
    )
    return f'<div class="row">{event}</div><div class="row">{season}</div>'


def front(version: str) -> str:
    """Return the front page (scores, one column per sample)."""
    out = ['<div class="sheet front">', _title_bar("SITTING")]
    out.append(
        '<div class="sit">'
        '<div style="flex:0 0 3.25in"><span class="k">Blotter mode</span>'
        f'<span class="tk">{_box(ticked=True)}<b>Individual trays</b></span>'
        f'<span class="tk">{_box()}Group (not used)</span></div>'
        '<div style="flex:1"><span class="k">Local date</span>'
        '<span class="wr"></span></div>'
        '<div style="flex:1"><span class="k">Time zone</span>'
        '<span class="wr"></span></div>'
        '<div style="flex:1"><span class="k">Recorder initials</span>'
        '<span class="wr"></span></div></div>'
    )
    out.append(
        '<div class="rule">Intensity 0 = you cannot smell it. Circle 0, write the '
        "times, initial the column, and leave the rest of that column blank.</div>"
    )
    out.append(
        _codes_band(
            "Sample answers",
            "Write the code from the atomizer. Circle one value per row.",
        )
    )
    out.append(_time_row("Time sprayed", "the blotter you smelled"))
    out.append(_time_row("Time first smelled"))
    out.append(_time_row("Time this column finished"))
    out.append(
        _simple_row("Do you recognize this?", _options("No", "Vaguely", "Exactly"))
    )
    out.append(
        _simple_row("Have you owned or worn it?", _options("Yes", "No", "Not sure"))
    )
    out.append(
        _group(
            "What you perceived",
            "Properties of the fragrance itself, whether or not you liked them.",
        )
    )
    out.extend(_scale_row(n, lo, hi, 5) for n, lo, hi in PERCEIVED_ROWS)
    out.append(
        _group(
            "How you responded",
            "Your own reaction. A fragrance can be strongly perceived and still "
            "disliked.",
        )
    )
    out.extend(_scale_row(n, lo, hi, top) for n, lo, hi, top in RESPONSE_ROWS)
    out.append(_group("How sure you are", "How much weight this record should carry."))
    out.extend(_scale_row(n, lo, hi, top) for n, lo, hi, top in SURE_ROWS)
    initials = (
        '<div class="init"><span>Evaluator initials</span>'
        '<span class="wr2"></span></div>'
    )
    out.append(
        '<div class="row last" style="min-height:22pt">'
        f"{_label('Column complete')}{_cells(initials)}</div>"
    )
    out.extend((_foot(1, version), "</div>"))
    return "".join(out)


def back(version: str) -> str:
    """Return the back page (setting, notes, ranking, sitting times)."""
    out = ['<div class="sheet back">', _title_bar("SITTING, SIDE 2")]
    out.append(_codes_band("Notes and ranking", "Same codes as the front.", small=True))
    out.append(
        _group(
            "Where and when would you wear it",
            "Tick all that fit, unless a line says tick only this.",
        )
    )
    out.append(_event_rows())
    out.append(
        '<div class="nnote">Use your own words. Do not copy a note list. Do not '
        "record passwords, medical details, or unrelated personal information.</div>"
    )
    out.append('<div class="notes">')
    for k, (name, sub, tall) in enumerate(NOTE_ROWS):
        cls = (" p" if tall else "") + (" last" if k == len(NOTE_ROWS) - 1 else "")
        out.append(
            f'<div class="row{cls}">{_label(name, sub)}{_cells(WRITE_AREA)}</div>'
        )
    out.append("</div>")
    heads = "".join(
        f'<span class="h">Sample {i} code{_write_box()}</span>'
        for i in range(1, SAMPLES + 1)
    )
    out.append(
        f'<div class="band" style="margin-top:8pt"><span class="t">Ranking</span>'
        f"{heads}</div>"
    )
    out.append(
        '<div class="rtext">Complete after all three columns are initialed. Rank '
        "only samples you could smell, 1 for the one you liked most. Samples can "
        "share a place: give two samples 1, and the next sample is 3.</div>"
    )
    choices = (
        f'<div class="lab"><span class="tk">{_box()}I would rather not rank</span>'
        f'<br><span class="tk">{_box()}I could not tell them apart</span></div>'
    )
    place = '<div class="pl"><small>Place</small><div class="rankbox"></div></div>'
    out.append(
        f'<div class="rank"><div class="row last">{choices}{_cells(place)}</div></div>'
    )
    times = "".join(
        f"<div><b>{name}</b>"
        '<div class="tm"><span>hh:mm:ss</span>'
        '<b class="wr3" style="display:block;margin:0"></b></div></div>'
        for name in ("Session start time", "Session end time", "Ranking time")
    )
    out.append(
        '<div class="times"><div class="th">Times for the whole sitting</div>'
        f'<div class="tg">{times}</div></div>'
    )
    out.extend((_foot(2, version), "</div>"))
    return "".join(out)


def render_html(version: str, css: str | None = None) -> str:
    """Return the complete two-page HTML document.

    Args:
        version: The sheet version marker printed in both footers.
        css: Stylesheet text; defaults to ``scripts/print/forms.css``.

    Returns:
        A standalone HTML document with the front and the back page.
    """
    style = css if css is not None else CSS_PATH.read_text(encoding="utf-8")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(version)}</title><style>{style}</style></head>"
        f"<body>{front(version)}{back(version)}</body></html>"
    )


def main(argv: list[str] | None = None) -> int:
    """Write the HTML file named on the command line.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv``).

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    args.output.write_text(render_html(args.version), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
