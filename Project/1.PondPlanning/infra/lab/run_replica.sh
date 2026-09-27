#!/usr/bin/env bash
# One self-contained replica of the app on a lab VM (no Docker, no systemd, no root).
#
# API + built SPA from one uvicorn process with the in-process adapters
# (memory persistence, thread-pool jobs, local object store) — ADR 0013's ports
# make that a configuration change, not a code change. The loop is the
# supervisor the VM lacks: if uvicorn exits for any reason it is restarted.
#
#   PORT=4000 infra/lab/run_replica.sh      (container port; the VM forwards it)
set -u
cd "$(dirname "$0")/../.."
PORT="${PORT:-4000}"
export POND_ENV=production
export POND_PERSISTENCE=memory POND_JOB_RUNNER=thread POND_OBJECT_STORE=local  # 202 at once; bulkhead pools
export POND_LOCAL_STORE_DIR="${POND_LOCAL_STORE_DIR:-$HOME/pond/store}"
export POND_RAINFALL_SOURCE=live            # arbitrary locations; recorded file is the last fallback
export POND_LANDCOVER_TIMEOUT_S="${POND_LANDCOVER_TIMEOUT_S:-12}"  # WorldCover/SoilGrids: flaky from here
export POND_RAINFALL_TIMEOUT_S="${POND_RAINFALL_TIMEOUT_S:-12}"    # reach the fallback provider sooner
export POND_GEOCODE_ENABLED=true
mkdir -p "$POND_LOCAL_STORE_DIR"
while true; do
  echo "$(date -Is) starting replica on :$PORT"
  .venv/bin/uvicorn scripts.single_server:app --host 0.0.0.0 --port "$PORT" \
    --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 30
  echo "$(date -Is) replica exited with $?; restarting in 3 s"
  sleep 3
done
