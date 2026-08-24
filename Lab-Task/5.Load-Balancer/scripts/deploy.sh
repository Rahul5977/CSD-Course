#!/usr/bin/env bash
# ============================================================================
# deploy.sh — rsync + (re)start services on the lab systems. Idempotent.
#
#   bash scripts/deploy.sh sys2|sys3|sys4    deploy one backend
#   bash scripts/deploy.sh state             deploy state service to sys1
#   bash scripts/deploy.sh lb                deploy load balancer to sys1
#   bash scripts/deploy.sh all               state + lb + all three backends
#
# Processes run inside named tmux sessions (systemd --user is offline on these
# boxes). Kills only OUR sessions, never other users' processes.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

# host alias / app port per system (macOS bash 3.2: no associative arrays)
ssh_host() { case "$1" in sys2) echo lbsys2;; sys3) echo lbsys3;; sys4) echo lbsys4;; esac; }
# D-008: every container's app binds 3000 — the lab NAT maps external 32XX -> container 3000.
app_port() { echo 3000; }
REMOTE_DIR="~/assignment5"
# sys1's address as seen from sys2/3/4 (Docker bridge — verified in Phase 0.3)
STATE_HOST="${STATE_HOST:-172.17.0.70}"
STATE_PORT=5269

# The lab boxes have no rsync; a tar pipe over ssh is just as idempotent.
push() {  # $1 = ssh alias, $2... = local dirs/files to copy
  local host="$1"; shift
  tar czf - --exclude data --exclude '*.log' "$@" | ssh "$host" "mkdir -p $REMOTE_DIR && cd $REMOTE_DIR && tar xzf -"
}
rsync_app() { push "$1" app; }

deploy_backend() {  # $1 = sys2|sys3|sys4
  local sys="$1" host="$(ssh_host "$1")" port="$(app_port "$1")"
  echo "== deploy backend -> $sys (${host}, port ${port}) =="
  ssh "$host" "mkdir -p $REMOTE_DIR"
  rsync_app "$host"
  # sys2-4 have no tmux and no system node: use ~/node/bin (install_node.sh)
  # and nohup+pidfile supervision. Kill ONLY our own recorded pid.
  ssh "$host" "
    set -e
    cd $REMOTE_DIR
    export PATH=\"\$HOME/node/bin:\$PATH\"
    command -v node >/dev/null || { echo 'no node — run scripts/install_node.sh first'; exit 1; }
    printf 'PORT=%s\nBACKEND_ID=%s\nSTATE_URL=http://%s:%s\nLOG_LEVEL=info\n' \
        '$port' '$sys' '$STATE_HOST' '$STATE_PORT' > .env
    if command -v tmux >/dev/null; then
      tmux kill-session -t backend 2>/dev/null || true
      tmux new-session -d -s backend \
        \"export PATH=\$HOME/node/bin:\\\$PATH; export \\\$(cat .env | xargs); node app/server.js >> backend.log 2>&1\"
    else
      [ -f backend.pid ] && kill \$(cat backend.pid) 2>/dev/null || true
      sleep 0.5
      nohup env \$(cat .env | xargs) node app/server.js >> backend.log 2>&1 < /dev/null &
      echo \$! > backend.pid
    fi
  "
  # wait for /health (checked from inside the box — external NAT may be closed)
  for i in $(seq 1 20); do
    if ssh "$host" "curl -sS -m 2 http://127.0.0.1:$port/health" 2>/dev/null | grep -q '"status":"ok"'; then
      echo "   $sys healthy ✔"; return 0
    fi
    sleep 1
  done
  echo "   $sys FAILED to become healthy"; ssh "$host" "tail -20 $REMOTE_DIR/backend.log"; return 1
}

deploy_state() {
  echo "== deploy state service -> sys1:$STATE_PORT =="
  ssh lbsys1 "mkdir -p $REMOTE_DIR"
  rsync_app lbsys1
  ssh lbsys1 "
    set -e
    cd $REMOTE_DIR
    tmux kill-session -t state 2>/dev/null || true
    tmux new-session -d -s state \
      'PORT=$STATE_PORT DATA_DIR=$REMOTE_DIR/data node app/state_service.js >> state.log 2>&1'
  "
  for i in $(seq 1 20); do
    if ssh lbsys1 "curl -sS -m 2 http://127.0.0.1:$STATE_PORT/health" 2>/dev/null | grep -q '"status":"ok"'; then
      echo "   state healthy ✔"; return 0
    fi
    sleep 1
  done
  echo "   state FAILED"; ssh lbsys1 "tail -20 $REMOTE_DIR/state.log"; return 1
}

deploy_lb() {
  echo "== deploy load balancer -> sys1:3269 =="
  ssh lbsys1 "mkdir -p $REMOTE_DIR/lb $REMOTE_DIR/logs"
  push lbsys1 lb
  ssh lbsys1 "
    set -e
    cd $REMOTE_DIR
    tmux kill-session -t lb 2>/dev/null || true
    # the LB catches SIGHUP (config reload), so tmux kill alone won't stop it —
    # kill our loadbalancer.py explicitly. The ^python3 anchor stops pkill -f
    # from matching this shell's own cmdline (which quotes the same path).
    pkill -f '^python3 lb/loadbalancer' 2>/dev/null || true
    for i in 1 2 3 4 5; do ss -tln | grep -q ':3000 ' || break; sleep 1; done
    tmux new-session -d -s lb \
      'cd $REMOTE_DIR && python3 lb/loadbalancer.py lb/lb.conf.json >> lb.log 2>&1'
  "
  for i in $(seq 1 15); do
    if ssh lbsys1 "curl -sS -m 2 http://127.0.0.1:3000/lb/health" 2>/dev/null | grep -q '"status":"ok"'; then
      echo "   lb healthy ✔"; return 0
    fi
    sleep 1
  done
  echo "   lb FAILED"; ssh lbsys1 "tail -20 $REMOTE_DIR/lb.log"; return 1
}

case "${1:?usage: deploy.sh sys2|sys3|sys4|state|lb|all}" in
  sys2|sys3|sys4) deploy_backend "$1" ;;
  state)          deploy_state ;;
  lb)             deploy_lb ;;
  all)            deploy_state; deploy_backend sys2; deploy_backend sys3; deploy_backend sys4; deploy_lb ;;
  *) echo "unknown target $1"; exit 1 ;;
esac
