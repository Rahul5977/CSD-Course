#!/usr/bin/env bash
# Host-side entry point. Builds the image, then runs every experiment in one container.
# Usage: scripts/run_all.sh [main|supp|big|wal|rest|all]      (default: all, about 30 minutes)
set -euo pipefail
LAB="$(cd "$(dirname "$0")/.." && pwd)"
# reuse the cached image if the registry is unreachable
docker build -q -t csd-fio:lab10 "$LAB/docker" >/dev/null || docker image inspect csd-fio:lab10 >/dev/null
docker volume create fio-lab >/dev/null
docker run --rm --name fio-lab10 \
  -v "$LAB":/lab -v fio-lab:/fio-lab \
  csd-fio:lab10 sh /lab/scripts/run_in_container.sh "${1:-all}" 2>&1 | tee "$LAB/results/run_${1:-all}.log"
