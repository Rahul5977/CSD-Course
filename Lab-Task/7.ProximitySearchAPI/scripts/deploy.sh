#!/usr/bin/env bash
# One-command deploy to a lab box (no internet there: wheels are downloaded here and pushed).
#
#   scripts/deploy.sh                 # default: lbsys2, container port 3000 (public 10.1.75.53:3270)
#   HOST=lbsys3 PORT=3000 scripts/deploy.sh
#   scripts/deploy.sh status | stop
#
# Remote layout: ~/assignment7/{app,data,requirements.txt,.venv,wheels,run.sh,server.log,supervisor.pid}
set -euo pipefail
HOST="${HOST:-lbsys2}"
PORT="${PORT:-3000}"
DIR=assignment7
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH=(ssh -o ConnectTimeout=8 -o BatchMode=yes "$HOST")

remote_stop='cd ~/'$DIR' 2>/dev/null || exit 0
if [ -f supervisor.pid ]; then kill "$(cat supervisor.pid)" 2>/dev/null || true; rm -f supervisor.pid; fi
if [ -f server.pid ]; then kill "$(cat server.pid)" 2>/dev/null || true; rm -f server.pid; fi
sleep 1'

remote_status='cd ~/'$DIR' && echo "supervisor: $(cat supervisor.pid 2>/dev/null) server: $(cat server.pid 2>/dev/null)";
ss -ltn | grep ":'$PORT' " || echo "nothing listening on :'$PORT'";
curl -s -m 3 localhost:'$PORT'/health; echo; tail -3 server.log 2>/dev/null'

case "${1:-deploy}" in
  stop)   "${SSH[@]}" "$remote_stop"; echo "stopped on $HOST"; exit 0 ;;
  status) "${SSH[@]}" "$remote_status"; exit 0 ;;
  deploy) ;;
  *) echo "usage: $0 [deploy|status|stop]"; exit 2 ;;
esac

# 1. Linux wheels for the box (x86_64, CPython 3.12), cached locally.
WHEELS="$ROOT/.wheelhouse"
if [ ! -f "$WHEELS/.complete" ]; then
  mkdir -p "$WHEELS"
  "$ROOT/.venv/bin/pip" download -q -d "$WHEELS" -r "$ROOT/requirements.txt" \
    --platform manylinux2014_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux_2_28_x86_64 \
    --python-version 3.12 --implementation cp --only-binary=:all:
  touch "$WHEELS/.complete"
fi

# 2. Supervisor: restarts uvicorn if it ever exits (the boxes have no cron/systemd/tmux).
cat > "$ROOT/.run.sh" <<EOF
#!/usr/bin/env bash
cd ~/$DIR
echo \$\$ > supervisor.pid
while true; do
  .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log >> server.log 2>&1 &
  echo \$! > server.pid
  wait \$!
  echo "\$(date -Is) uvicorn exited with \$?, restarting in 1 s" >> server.log
  sleep 1
done
EOF

# 3. Push code + data + wheels (no rsync on the boxes; strip macOS xattrs).
"${SSH[@]}" "$remote_stop"
cp "$ROOT/.run.sh" "$ROOT/run.sh.deploy"
( cd "$ROOT" && COPYFILE_DISABLE=1 tar --no-xattrs -czf - \
    --exclude='__pycache__' app data requirements.txt -C "$ROOT" .wheelhouse run.sh.deploy ) \
  | "${SSH[@]}" "mkdir -p ~/$DIR && cd ~/$DIR && rm -rf app wheels && tar xzf - 2>/dev/null && mv .wheelhouse wheels && mv run.sh.deploy run.sh && chmod +x run.sh"
rm -f "$ROOT/.run.sh" "$ROOT/run.sh.deploy"

# 4. Offline install + start detached.
# The boxes lack ensurepip, so the venv borrows the system pip (--system-site-packages).
"${SSH[@]}" "cd ~/$DIR && rm -rf .venv && python3 -m venv --without-pip --system-site-packages .venv \
  && .venv/bin/python -m pip install -q --no-index --find-links wheels -r requirements.txt \
  && { setsid nohup ./run.sh > /dev/null 2>&1 < /dev/null & } && sleep 4; $remote_status"
echo "deployed to $HOST:$PORT"
