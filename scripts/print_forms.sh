#!/usr/bin/env bash
# Render the facilitated blind session sheet to a 4-page duplex PDF (two US Letter sheets).
# Needs pandoc and Google Chrome. Output goes to tmp_cleanup/print/ (gitignored) unless a directory is given.
# Usage: scripts/print_forms.sh [output-dir]
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
src="$root/docs/facilitated-session-sheet.md"
css="$root/scripts/print/forms.css"
out="${1:-$root/tmp_cleanup/print}"
chrome="${CHROME:-google-chrome}"
want_pages=4

version="$(sed -n 's/^Sheet version: \x60\(.*\)\x60$/\1/p' "$src" | head -n 1)"
[ -n "$version" ] || { echo "no 'Sheet version:' line found in $src" >&2; exit 1; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$out"

sed "s|@@VERSION@@|$version|g" "$css" > "$work/forms.css"
pandoc -f markdown+pipe_tables+task_lists -t html5 -s --section-divs --embed-resources \
  --css="$work/forms.css" "$src" -o "$work/sheet.html"
"$chrome" --headless=new --no-sandbox --disable-gpu --no-pdf-header-footer \
  --user-data-dir="$work/profile" --print-to-pdf="$out/facilitated-session-sheet.pdf" "$work/sheet.html" 2>/dev/null

pages="$(grep -a -c '/Type /Page$' "$out/facilitated-session-sheet.pdf" || true)"
echo "wrote $out/facilitated-session-sheet.pdf ($pages pages, expected $want_pages)"
[ "$pages" -eq "$want_pages" ] || { echo "page count is not $want_pages: check the layout" >&2; exit 1; }
