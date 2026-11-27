#!/usr/bin/env bash
# Render the facilitated paper forms to PDF. Needs pandoc and Google Chrome. Output goes to tmp_cleanup/print/
# (gitignored) unless a directory is given. One run writes these PDFs:
#   facilitated-session-sheet.pdf        2 pages: the generic two-sided master (one US Letter sheet, duplex long edge);
#                                        fails if the count differs. Built by scripts/render_session_sheet.py, forms.css
#   facilitated-session-sheet-notes.pdf  facilitator notes (rules, transcription, tracker); page count reported only
#   facilitated-rules-card.pdf           1 page, one-time handout, 11 pt minimum text; fails if the count differs
#   facilitated-consent-line.pdf         1 page, one-time handout for the evaluator packet; fails if the count differs
#   facilitated-property-guide.pdf       1 page, one-time handout, 11 pt minimum text; fails if the count differs
#   facilitated-conditions-slip.pdf      page count reported only. document.css
#   facilitated-run-sheet.pdf            page count reported only. document.css
# The rules card, the consent line and the facilitator notes are sections of docs/facilitated-session-sheet.md
# (classes .rules-card, .consent-line, .facilitator); the handout renders hide every other section. The property guide is a
# reading aid outside the P6.3 instrument and adds no recorded field.
# Usage: scripts/print_forms.sh [output-dir]
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
docs="$root/docs"
css_dir="$root/scripts/print"
out="${1:-$root/tmp_cleanup/print}"
chrome="${CHROME:-google-chrome}"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$out"

# count_pages <pdf>
count_pages() { grep -a -c '/Type /Page$' "$1" || true; }

# check_pages <name> <pdf> <version label> <expected pages or "report">
check_pages() {
  local name="$1" pdf="$2" version="$3" want="$4" pages
  pages="$(count_pages "$pdf")"
  if [ "$want" = "report" ]; then
    echo "wrote $pdf ($pages pages, footer: $version)"
  else
    echo "wrote $pdf ($pages pages, expected $want, footer: $version)"
    [ "$pages" -eq "$want" ] || { echo "$name: page count is not $want: check the layout" >&2; exit 1; }
  fi
}

# print_html <html> <pdf> <profile name>
print_html() {
  "$chrome" --headless=new --no-sandbox --disable-gpu --no-pdf-header-footer \
    --user-data-dir="$work/profile-$3" --print-to-pdf="$2" "$1" 2>/dev/null
}

# render <source doc> <output name> <css file> <version label> <expected pages or "report"> [only section class]
# With a section class, every other section (and the title block) is hidden, so one source can feed several handouts.
render() {
  local doc="$1" name="$2" css="$3" version="$4" want="$5" only="${6:-}"
  local src="$docs/$doc.md" pdf="$out/$name.pdf"
  sed "s|@@VERSION@@|$version|g" "$css_dir/$css" > "$work/$name.css"
  if [ -n "$only" ]; then
    echo "body > *:not(section.$only) { display: none !important; }" >> "$work/$name.css"
  fi
  pandoc -f markdown+pipe_tables+task_lists -t html5 -s --section-divs --embed-resources \
    --css="$work/$name.css" "$src" -o "$work/$name.html"
  print_html "$work/$name.html" "$pdf" "$name"
  check_pages "$name" "$pdf" "$version" "$want"
}

# Pull a version id out of a source file; fail loudly rather than print an empty footer.
version_of() {
  local v
  v="$(sed -n "$2" "$docs/$1.md" | head -n 1)"
  [ -n "$v" ] || { echo "no version id found in docs/$1.md" >&2; exit 1; }
  printf '%s' "$v"
}

sheet_version="$(version_of facilitated-session-sheet 's/^Sheet version: \x60\(.*\)\x60$/\1/p')"
guide_version="$(version_of facilitated-property-guide 's/^\(facilitated-property-guide v[0-9][0-9.]*\)$/\1/p')"
slip_version="$(version_of facilitated-conditions-slip 's/^Slip version: \x60\(.*\)\x60$/\1/p')"

# The generic two-sided master: HTML built by render_session_sheet.py, printed as exactly two pages.
sheet_pdf="$out/facilitated-session-sheet.pdf"
python3 "$root/scripts/render_session_sheet.py" "$work/sheet.html" --version "$sheet_version"
print_html "$work/sheet.html" "$sheet_pdf" sheet
check_pages facilitated-session-sheet "$sheet_pdf" "$sheet_version" 2

render facilitated-session-sheet facilitated-session-sheet-notes document.css "$sheet_version" report facilitator
render facilitated-session-sheet facilitated-rules-card handout.css "$sheet_version" 1 rules-card
render facilitated-session-sheet facilitated-consent-line handout.css "$sheet_version" 1 consent-line
render facilitated-property-guide facilitated-property-guide handout.css "$guide_version" 1
render facilitated-conditions-slip facilitated-conditions-slip document.css "$slip_version" report
render facilitated-run-sheet facilitated-run-sheet document.css "Facilitator run sheet" report
