#!/usr/bin/env bash
# ============================================================================
# run_interleaved.sh — drift-fair A/B/C measurement matrix (see D-010).
#
# The lab containers share one multi-tenant physical host whose background
# load varies by the hour, so sequential per-config sweeps are confounded.
# This runner interleaves the three configs: for every (concurrency, rep)
# round it runs A (direct sys2), B (LB x1) and C (LB x3) BACK-TO-BACK in
# shuffled order, so each cross-config comparison shares the same host
# conditions. Skips runs whose result file already exists (safe to re-run).
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

LB_URL="${LB_URL:-http://10.1.75.53:3269}"
DIRECT_URL="${DIRECT_URL:-http://10.1.75.53:3270}"
LEVELS=(${LEVELS:-1 10 25 50 100 200 400})
REPS=${REPS:-3}
DUR=${DUR:-60}
WARM=${WARM:-10}
COOL=${COOL:-15}
MANIFEST=evidence/07_run_manifest.md

mkdir -p results/raw results/sysmetrics
[ -f "$MANIFEST" ] || printf "# Run manifest\n\n| run_id | config | conc | rep | started | result |\n|---|---|---|---|---|---|\n" > "$MANIFEST"

set_pool() {  # $1 = "sys2" or "sys2 sys3 sys4"
  ssh lbsys1 "python3 - <<'EOF'
import json
conf_path = 'assignment5/lb/lb.conf.json'
conf = json.load(open(conf_path))
want = '$1'.split()
all_b = json.load(open('assignment5/lb/backends.all.json'))
conf['backends'] = [b for b in all_b if b['id'] in want]
json.dump(conf, open(conf_path, 'w'), indent=2)
EOF"
  curl -sS -m 10 --retry 4 --retry-delay 3 --retry-all-errors -X POST "$LB_URL/lb/reload" > /dev/null
  sleep 3
}

restart_backends() {
  for s in sys2 sys3 sys4; do bash scripts/deploy.sh $s > /dev/null 2>&1 || true; done
  sleep 3
}

sample_sysmetrics() {
  local rid="$1"
  for s in 2 3 4; do
    ssh -o BatchMode=yes lbsys$s "
      end=\$((SECONDS + $DUR + 5))
      while [ \$SECONDS -lt \$end ]; do
        cpu=\$(awk '/^cpu /{print \$2+\$3+\$4, \$2+\$3+\$4+\$5}' /proc/stat)
        rss=\$(ps -o rss= -C node 2>/dev/null | paste -sd+ | bc 2>/dev/null || echo 0)
        echo \"\$(date +%s) \$cpu \$rss\"
        sleep 1
      done" > "results/sysmetrics/${rid}_sys$s.txt" 2>/dev/null &
  done
}

one_run() {  # $1 config, $2 url, $3 conc, $4 rep
  local cfg="$1" url="$2" c="$3" rep="$4"
  local rid="${cfg}_c${c}_rep${rep}"
  if [ -f "results/raw/${rid}.json" ]; then
    echo "-- $rid already exists, skipping"; return 0
  fi
  echo "== RUN $rid  ($(date +%T)) =="
  sample_sysmetrics "$rid"
  if ! python3 loadgen/loadgen.py --url "$url" --concurrency "$c" \
      --duration "$DUR" --warmup "$WARM" --run-id "$rid" \
      > "logs/loadgen_${rid}.log" 2>&1; then
    echo "   RUN FAILED — see logs/loadgen_${rid}.log (continuing)"
    wait || true; sleep "$COOL"; return 0
  fi
  wait || true
  local tput=$(python3 -c "import json;print(json.load(open('results/raw/${rid}.json'))['summary']['throughput_rps'])")
  printf "| %s | %s | %s | %s | %s | %s rps |\n" "$rid" "$cfg" "$c" "$rep" "$(date -Iseconds)" "$tput" >> "$MANIFEST"
  echo "   done: $tput req/s"
  sleep "$COOL"
}

run_cfg() {  # $1 config, $2 conc, $3 rep — set pool then run
  case "$1" in
    A) one_run A "$DIRECT_URL" "$2" "$3" ;;
    B) set_pool "sys2";           one_run B "$LB_URL" "$2" "$3" ;;
    C) set_pool "sys2 sys3 sys4"; one_run C "$LB_URL" "$2" "$3" ;;
  esac
}

for c in "${LEVELS[@]}"; do
  echo "#### LEVEL c=$c — fresh backends ####"
  restart_backends
  for r in $(seq 1 "$REPS"); do
    # shuffle config order each round so drift is spread evenly across configs
    order=$(python3 -c "import random; l=['A','B','C']; random.shuffle(l); print(' '.join(l))")
    echo "-- round c=$c rep=$r order: $order"
    for cfg in $order; do run_cfg "$cfg" "$c" "$r"; done
  done
done
echo "interleaved A/B/C matrix complete."
