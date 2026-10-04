#!/usr/bin/env bash
# Config D — failover under load: 90 s run at c=100 against the LB with all
# three backends; sys3's backend is killed at t=30 s and redeployed at t=60 s.
# The kill/restart moments are annotated into the result JSON for the chart.
set -euo pipefail
cd "$(dirname "$0")/.."
LB_URL="${LB_URL:-http://10.1.75.53:3269}"
RID="D_failover_c100"

echo "== ensuring all three backends are in the pool =="
ssh lbsys1 "python3 - <<'EOF'
import json
conf = json.load(open('assignment5/lb/lb.conf.json'))
conf['backends'] = json.load(open('assignment5/lb/backends.all.json'))
conf['algorithm'] = 'round_robin'
json.dump(conf, open('assignment5/lb/lb.conf.json', 'w'), indent=2)
EOF"
curl -sS -m 5 -X POST "$LB_URL/lb/reload" > /dev/null
sleep 6

echo "== starting 90 s loadgen run (c=100) =="
python3 loadgen/loadgen.py --url "$LB_URL" --concurrency 100 --duration 90 \
    --warmup 10 --run-id "$RID" > "logs/loadgen_${RID}.log" 2>&1 &
LG=$!

sleep 30
echo "== t=30s: killing sys3 backend =="
ssh lbsys3 'kill $(cat assignment5/backend.pid) 2>/dev/null' && echo "   killed"
KILL_T=30
sleep 8
curl -sS -m 5 "$LB_URL/lb/stats" | python3 -c "import json,sys; d=json.load(sys.stdin); print('   health during outage:', [(b['id'],b['healthy']) for b in d['backends']])" | tee evidence/05_failover.txt

sleep 22
echo "== t=60s: restarting sys3 =="
bash scripts/deploy.sh sys3 > /dev/null 2>&1 && echo "   restarted"

wait $LG
python3 - <<EOF
import json
p = 'results/raw/${RID}.json'
d = json.load(open(p))
d['summary']['kill_at_s'] = ${KILL_T}
d['summary']['restart_at_s'] = 60
json.dump(d, open(p, 'w'))
s = d['summary']
print(f"failover run: {s['total_requests']} reqs, {s['errors']} errors "
      f"({s['error_rate_pct']}%), {s['throughput_rps']} rps")
print('distribution:', s['backend_distribution'])
EOF
sleep 5
curl -sS -m 5 "$LB_URL/lb/stats" | python3 -c "import json,sys; d=json.load(sys.stdin); print('post-recovery health:', [(b['id'],b['healthy']) for b in d['backends']])" | tee -a evidence/05_failover.txt
