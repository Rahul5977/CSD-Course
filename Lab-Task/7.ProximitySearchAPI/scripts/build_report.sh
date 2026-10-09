#!/usr/bin/env bash
# Builds report/REPORT_12341680.pdf from report/report.tex (needs tectonic: brew install tectonic).
# Run scripts/analyze.py first if the tables or plots need updating.
set -euo pipefail
cd "$(dirname "$0")/../report"
tectonic -X compile report.tex
mv report.pdf REPORT_12341680.pdf
echo "wrote report/REPORT_12341680.pdf"
