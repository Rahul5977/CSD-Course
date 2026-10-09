#!/usr/bin/env bash
# Terminal evidence for the report: test run, curl examples, load test.
#   scripts/capture_evidence.sh http://127.0.0.1:8077 local
#   scripts/capture_evidence.sh http://10.1.75.53:3270 public
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
B="${1:-http://127.0.0.1:8077}"
TAG="${2:-local}"
OUT="$ROOT/report/terminal_captures"
mkdir -p "$OUT"
cd "$ROOT"

if [ "$TAG" = local ]; then
  {
    echo '$ .venv/bin/python -m pytest -v'
    .venv/bin/python -m pytest -v -p no:warnings 2>&1 | grep -E "PASSED|FAILED|passed|failed" | sed 's/ *\[ *[0-9]*%\]//'
  } > "$OUT/01_tests.txt"
fi

{
  for u in "/health" \
           "/search/?lat=0.74&long=0.6&cat=bank&rad=0.1" \
           "/search?lat=0.5&long=0.5&cat=cafe&rad=0.12" \
           "/search/?lat=0.2&long=0.9&cat=Hospital&rad=0.2" \
           "/search/?lat=0.5&long=0.5&cat=spaceport&rad=0.1" \
           "/search/?lat=0.5&long=abc&cat=cafe&rad=0.1" \
           "/search/?lat=0.5&long=0.5&cat=cafe"; do
    echo "\$ curl -s '$B$u'"
    curl -s -m 10 -w "   [HTTP %{http_code}]" "$B$u"
    printf '\n\n'
  done
} > "$OUT/02_curl_$TAG.txt"

{
  echo "\$ scripts/loadtest.py $B --requests 2000 --concurrency 1"
  .venv/bin/python scripts/loadtest.py "$B" --requests 2000 --concurrency 1
  echo "\$ scripts/loadtest.py $B --requests 5000 --concurrency 32"
  .venv/bin/python scripts/loadtest.py "$B" --requests 5000 --concurrency 32
} > "$OUT/03_loadtest_$TAG.txt" 2>&1

tail -n 2 "$OUT/01_tests.txt" 2>/dev/null
cat "$OUT/02_curl_$TAG.txt" "$OUT/03_loadtest_$TAG.txt"
