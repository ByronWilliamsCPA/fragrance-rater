#!/usr/bin/env bash
# Render the facilitated paper forms to PDF. Needs pandoc and Google Chrome. Output goes to tmp_cleanup/print/
# (gitignored) unless a directory is given. One run writes four PDFs:
#   facilitated-session-sheet.pdf    4 pages (two US Letter sheets, duplex); fails if the count differs. forms.css
#   facilitated-property-guide.pdf   1 page, 11 pt minimum text; fails if the count differs. handout.css
#   facilitated-conditions-slip.pdf  page count reported only. document.css
#   facilitated-run-sheet.pdf        page count reported only. document.css
# The property guide is a reading aid outside the P6.3 instrument: it is rendered here only so the printed copy
# matches the merged source, and it adds no recorded field.
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

# render <name> <css file> <version label> <expected pages or "report">
render() {
  local name="$1" css="$2" version="$3" want="$4"
  local src="$docs/$name.md" pdf="$out/$name.pdf" pages
  sed "s|@@VERSION@@|$version|g" "$css_dir/$css" > "$work/$name.css"
  pandoc -f markdown+pipe_tables+task_lists -t html5 -s --section-divs --embed-resources \
    --css="$work/$name.css" "$src" -o "$work/$name.html"
  "$chrome" --headless=new --no-sandbox --disable-gpu --no-pdf-header-footer \
    --user-data-dir="$work/profile-$name" --print-to-pdf="$pdf" "$work/$name.html" 2>/dev/null
  pages="$(grep -a -c '/Type /Page$' "$pdf" || true)"
  if [ "$want" = "report" ]; then
    echo "wrote $pdf ($pages pages, footer: $version)"
  else
    echo "wrote $pdf ($pages pages, expected $want, footer: $version)"
    [ "$pages" -eq "$want" ] || { echo "$name: page count is not $want: check the layout" >&2; exit 1; }
  fi
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

render facilitated-session-sheet forms.css "$sheet_version" 4
render facilitated-property-guide handout.css "$guide_version" 1
render facilitated-conditions-slip document.css "$slip_version" report
render facilitated-run-sheet document.css "Facilitator run sheet" report
