#!/usr/bin/env bash
# Stop every service we started, on every system. Only kills OUR tmux
# sessions (state, lb, backend) — never other users' processes.
set -u
for h in lbsys1 lbsys2 lbsys3 lbsys4; do
  echo "== $h =="
  ssh -o BatchMode=yes -o ConnectTimeout=6 "$h" "
    for s in state lb backend; do
      tmux kill-session -t \$s 2>/dev/null && echo \"  stopped \$s\" || true
    done
  " 2>/dev/null || echo "  (unreachable)"
done
echo "done."
