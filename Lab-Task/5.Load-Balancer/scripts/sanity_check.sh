#!/usr/bin/env bash
# One command that prints the health of the whole system, local view.
# Green = HTTP 200 with status ok.
set -u
LB_URL="${LB_URL:-http://10.1.75.53:3269}"
check() {
  local name="$1" url="$2"
  local out
  out=$(curl -sS -m 5 "$url" 2>&1)
  if echo "$out" | grep -q '"status":"ok"'; then
    echo "✅ $name  $url  $(echo "$out" | head -c 120)"
  else
    echo "❌ $name  $url  $out"
  fi
}
echo "== sanity check $(date) =="
check "LB           " "$LB_URL/health"
curl -sS -m 5 "$LB_URL/lb/stats" 2>&1 | grep -q '"algorithm"' \
  && echo "✅ LB stats      $LB_URL/lb/stats" || echo "❌ LB stats      $LB_URL/lb/stats"
for s in 2 3 4; do
  ssh -o BatchMode=yes -o ConnectTimeout=5 lbsys$s "curl -sS -m 4 http://127.0.0.1:3000/health" 2>/dev/null \
    | grep -q '"status":"ok"' && echo "✅ backend sys$s (via ssh localhost:3000)" || echo "❌ backend sys$s"
done
ssh -o BatchMode=yes -o ConnectTimeout=5 lbsys1 "curl -sS -m 4 http://127.0.0.1:5269/health" 2>/dev/null \
  | grep -q '"status":"ok"' && echo "✅ state service sys1:5269" || echo "❌ state service sys1:5269"
