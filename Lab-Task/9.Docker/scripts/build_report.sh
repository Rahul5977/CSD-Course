#!/usr/bin/env bash
# Builds report/RahulRaj_Lab9_Report.pdf from report/report.tex (needs tectonic: brew install tectonic).
# The terminal figures are rendered from report/captures/*.txt by scripts/render_terminal.py.
set -euo pipefail
cd "$(dirname "$0")/../report"
tectonic -X compile report.tex
mv report.pdf RahulRaj_Lab9_Report.pdf
echo "wrote report/RahulRaj_Lab9_Report.pdf"
