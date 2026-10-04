#!/usr/bin/env bash
# 5-minute scripted live demo for the evaluation.
# Shows: health, distribution, a short load burst, live failover, recovery.
set -u
cd "$(dirname "$0")/.."
LB=http://10.1.75.53:3269
pause() { echo; read -p "--- ENTER for next step ---"; echo; }

echo "STEP 1 — whole-system health"
bash scripts/sanity_check.sh
pause

echo "STEP 2 — round-robin distribution (12 requests)"
for i in $(seq 1 12); do curl -sS -m 3 $LB/whoami | python3 -c "import json,sys;print(json.load(sys.stdin)['backend'],end=' ')"; done; echo
pause

echo "STEP 3 — live stats"
curl -sS $LB/lb/stats | python3 -m json.tool | head -40
echo "(dashboard: $LB/lb/ in a browser)"
pause

echo "STEP 4 — 30-second load burst at c=50"
python3 loadgen/loadgen.py --url $LB --concurrency 50 --duration 30 --warmup 5 --run-id demo_burst | tail -25
pause

echo "STEP 5 — kill sys3's backend mid-traffic, requests keep succeeding"
( for i in $(seq 1 40); do curl -sS -m 3 $LB/whoami | python3 -c "import json,sys;print(json.load(sys.stdin)['backend'],end=' ')" || echo -n "ERR "; sleep 0.3; done; echo ) &
sleep 2
ssh lbsys3 'kill $(cat assignment5/backend.pid) 2>/dev/null' && echo "[sys3 backend killed]"
wait
curl -sS $LB/lb/stats | python3 -c "import json,sys; print([(b['id'],b['healthy']) for b in json.load(sys.stdin)['backends']])"
pause

echo "STEP 6 — recovery"
bash scripts/deploy.sh sys3 | tail -1
sleep 8
curl -sS $LB/lb/stats | python3 -c "import json,sys; print([(b['id'],b['healthy']) for b in json.load(sys.stdin)['backends']])"
echo "demo complete."
