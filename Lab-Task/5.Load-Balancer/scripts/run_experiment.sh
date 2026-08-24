#!/usr/bin/env bash
# ============================================================================
# run_experiment.sh — the full measurement matrix, reproducible in one command.
#
#   bash scripts/run_experiment.sh            # everything (B, C, then extras)
#   bash scripts/run_experiment.sh B          # only config B (LB x1: sys2)
#   bash scripts/run_experiment.sh C          # only config C (LB x3)
#   bash scripts/run_experiment.sh A          # direct-to-sys2 baseline
#   bash scripts/run_experiment.sh E          # algorithm sweep at c=100
#
# Design (locked in ROADMAP Phase 7):
#   concurrency sweep 1 10 25 50 100 200 400, 60 s per run, 10 s warm-up
#   discarded, 3 repetitions, 15 s cooldown, run order randomised per config.
#   Backend CPU/mem sampled every 1 s over SSH during every run.
#   Pool switching between B and C is a config change + POST /lb/reload.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

LB_URL="${LB_URL:-http://10.1.75.53:3269}"        # public URL -> LB
DIRECT_URL="${DIRECT_URL:-http://10.1.75.53:3270}" # external -> sys2:3000 direct
LEVELS=(${LEVELS:-1 10 25 50 100 200 400})
REPS=${REPS:-3}
DUR=${DUR:-60}
WARM=${WARM:-10}
COOL=${COOL:-15}
MANIFEST=evidence/07_run_manifest.md

mkdir -p results/raw results/sysmetrics
[ -f "$MANIFEST" ] || printf "# Run manifest\n\n| run_id | config | conc | rep | started | result |\n|---|---|---|---|---|---|\n" > "$MANIFEST"

# ── helpers ─────────────────────────────────────────────────────────────────
set_pool() {  # $1 = "sys2" or "sys2 sys3 sys4"  → rewrite remote lb.conf.json pool
  ssh lbsys1 "python3 - <<'EOF'
import json
conf_path = 'assignment5/lb/lb.conf.json'
conf = json.load(open(conf_path))
want = '$1'.split()
all_b = json.load(open('assignment5/lb/backends.all.json'))
conf['backends'] = [b for b in all_b if b['id'] in want]
json.dump(conf, open(conf_path, 'w'), indent=2)
print('pool ->', [b['id'] for b in conf['backends']])
EOF"
  curl -sS -m 5 -X POST "$LB_URL/lb/reload" > /dev/null
  sleep 3
}

set_algo() {  # $1 = algorithm name
  ssh lbsys1 "python3 - <<'EOF'
import json
conf_path = 'assignment5/lb/lb.conf.json'
conf = json.load(open(conf_path))
conf['algorithm'] = '$1'
json.dump(conf, open(conf_path, 'w'), indent=2)
EOF"
  curl -sS -m 5 -X POST "$LB_URL/lb/reload" > /dev/null
  sleep 2
}

restart_backends() {
  for s in sys2 sys3 sys4; do bash scripts/deploy.sh $s > /dev/null 2>&1 || true; done
  sleep 3
}

sample_sysmetrics() {  # $1 run_id — background CPU/mem sampler over SSH
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
  python3 loadgen/loadgen.py --url "$url" --concurrency "$c" \
      --duration "$DUR" --warmup "$WARM" --run-id "$rid" \
      > "logs/loadgen_${rid}.log" 2>&1 || { echo "   RUN FAILED — see logs/loadgen_${rid}.log"; return 1; }
  wait || true
  local tput=$(python3 -c "import json;print(json.load(open('results/raw/${rid}.json'))['summary']['throughput_rps'])")
  printf "| %s | %s | %s | %s | %s | %s rps |\n" "$rid" "$cfg" "$c" "$rep" "$(date -Iseconds)" "$tput" >> "$MANIFEST"
  echo "   done: $tput req/s"
  sleep "$COOL"
}

sweep() {  # $1 config, $2 url
  local cfg="$1" url="$2"
  # randomise (level, rep) order to spread time-of-day drift
  local jobs=()
  for c in "${LEVELS[@]}"; do for r in $(seq 1 "$REPS"); do jobs+=("$c:$r"); done; done
  local shuffled=$(printf "%s\n" "${jobs[@]}" | python3 -c "import sys,random; l=sys.stdin.read().split(); random.shuffle(l); print(' '.join(l))")
  for j in $shuffled; do
    one_run "$cfg" "$url" "${j%%:*}" "${j##*:}"
  done
}

TARGET="${1:-all}"
want() { [ "$TARGET" = all ] || [ "$TARGET" = "$1" ]; }   # bash-3.2-safe dispatch

if want B; then
  echo "#### CONFIG B — LB with sys2 only ####"
  restart_backends; set_algo round_robin; set_pool "sys2"
  sweep B "$LB_URL"
fi
if want C; then
  echo "#### CONFIG C — LB with sys2+sys3+sys4 ####"
  restart_backends; set_algo round_robin; set_pool "sys2 sys3 sys4"
  sweep C "$LB_URL"
fi
if want A; then
  echo "#### CONFIG A — direct to sys2 (baseline) ####"
  restart_backends
  sweep A "$DIRECT_URL"
fi
if want E; then
  echo "#### CONFIG E — algorithm sweep at c=100 ####"
  restart_backends; set_pool "sys2 sys3 sys4"
  for algo in round_robin least_connections weighted_round_robin ip_hash; do
    set_algo "$algo"
    for r in 1 2 3; do one_run "E_${algo}" "$LB_URL" 100 "$r"; done
  done
  set_algo round_robin
fi
echo "experiment target '$TARGET' complete."
