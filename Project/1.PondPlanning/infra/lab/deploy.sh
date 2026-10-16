#!/usr/bin/env bash
# Redeploy the current working tree to the four lab replicas (lbsys1-4).
#
# For each VM: copy the backend (app/, scripts/, infra/, pyproject.toml, uv.lock) over
# ~/pond/app, `uv sync --no-dev` (retried: the campus uplink resets connections), then kill
# uvicorn so run_replica.sh's supervisor loop restarts it on the new code. The frontend build
# (web/dist) is unchanged unless DIST=1. Finally checks /health on every replica and the LB.
#
#   infra/lab/deploy.sh            # all four
#   HOSTS="lbsys2" infra/lab/deploy.sh
#   DIST=1 infra/lab/deploy.sh     # also ship web/dist (after `make web-build`)
set -u
cd "$(dirname "$0")/../.."
HOSTS="${HOSTS:-lbsys1 lbsys2 lbsys3 lbsys4}"
PUBLIC="http://10.1.75.53"
port() { case "$1" in lbsys1) echo 4269;; lbsys2) echo 4270;; lbsys3) echo 4271;; lbsys4) echo 5272;; esac; }  # bash 3.2 (macOS): no assoc arrays

paths=(app scripts infra pyproject.toml uv.lock)
[ "${DIST:-0}" = 1 ] && paths+=(web/dist)
bundle="$(mktemp -t pond-deploy).tgz"
tar czf "$bundle" --exclude='__pycache__' "${paths[@]}"
echo "bundle: $(du -h "$bundle" | cut -f1)"

for h in $HOSTS; do
  echo "== $h: copy"
  ssh "$h" 'cd ~/pond/app && tar xzf -' < "$bundle" || { echo "$h: copy failed"; continue; }
  echo "== $h: uv sync"
  ssh "$h" 'cd ~/pond/app && for i in 1 2 3 4 5; do ~/.local/bin/uv sync --no-dev -q && exit 0; echo "retry $i"; sleep 5; done; exit 1' \
    || { echo "$h: uv sync failed — replica left on the old code"; continue; }
  echo "== $h: restart (the supervisor loop brings uvicorn back)"
  ssh "$h" 'pkill -f "uvicorn scripts.single_server"' || true
done
rm -f "$bundle"

echo "== health (replicas need ~10 s)"
sleep 12
for h in $HOSTS; do
  printf '%-7s %s:%s  ' "$h" "$PUBLIC" "$(port "$h")"
  curl -s -m 8 --retry 3 -o /dev/null -w '%{http_code}\n' "$PUBLIC:$(port "$h")/health" || echo down
done
printf 'LB      %s:4272  ' "$PUBLIC"; curl -s -m 8 --retry 3 -o /dev/null -w '%{http_code}\n' "$PUBLIC:4272/health"
