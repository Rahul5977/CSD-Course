#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-http://localhost:5000}"
IMG="sample.jpg"
OUT_DIR="output"

mkdir -p "$OUT_DIR"

echo "== GET / =="
curl -s -w "  -> HTTP %{http_code}\n" "$HOST/"

for route in gray blur edges contours; do
  echo "== POST /$route =="
  curl -s -o "$OUT_DIR/${route}_output.jpg" \
       -w "  -> HTTP %{http_code}\n" \
       -X POST -F "image=@${IMG}" \
       "$HOST/$route"
done

echo "== POST /gray with no file (expect 400) =="
curl -s -w "  -> HTTP %{http_code}\n" -X POST "$HOST/gray"
echo

echo "Done. Outputs saved in $OUT_DIR/"
