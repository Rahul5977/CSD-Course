#!/usr/bin/env python3
"""
loadbalancer.py — HTTP/WebSocket reverse-proxy load balancer.

Assignment 5, CSD course. Runs on sys1 and spreads traffic from
http://10.1.75.53:3269 across the messaging-app backends on sys2/sys3/sys4.

Pure Python 3 standard library — no pip, no root, no external processes.

Features
--------
* Four selection algorithms, switchable in lb.conf.json:
    round_robin           each request goes to the next healthy backend
    least_connections     the backend with the fewest in-flight requests
    weighted_round_robin  smooth WRR honouring per-backend "weight"
    ip_hash               same client IP -> same backend (sticky)
* Active health checks: a background thread polls every backend's /health;
  a backend is ejected after `fail_threshold` consecutive misses and
  re-admitted after `rise_threshold` consecutive successes.
* Passive health checks: a connect failure during proxying ejects the backend
  immediately and the request is retried on the next healthy backend
  (only when nothing was sent upstream yet — safe for any method).
* WebSocket support: an Upgrade request is pinned to one backend and the
  connection is pumped byte-for-byte in both directions until either side
  closes (the LB stays out of the framing).
* Proxy headers: adds X-Forwarded-For, X-Real-IP, X-Forwarded-Proto,
  preserves Host, strips hop-by-hop headers.
* Upstream connection pooling + client keep-alive so the LB itself is not
  the bottleneck.
* Observability: per-request CSV access log, JSON stats at /lb/stats and a
  small auto-refreshing HTML dashboard at /lb/ (both served by the LB
  itself on the public port — only port 3269 is NAT-forwarded in this lab).
  /lb/reload re-reads lb.conf.json without dropping connections.

Usage:  python3 loadbalancer.py [path/to/lb.conf.json]
"""

import json
import os
import signal
import socket
import sys
import threading
import time
from collections import deque

# ───────────────────────────── configuration ────────────────────────────────

CONF_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "lb.conf.json")

DEFAULTS = {
    "listen_host": "0.0.0.0",
    "listen_port": 3269,
    "algorithm": "round_robin",
    "backends": [],                 # [{"id": "sys2", "host": "...", "port": 3270, "weight": 1}]
    "health_interval_s": 3,
    "health_timeout_s": 2,
    "fail_threshold": 2,
    "rise_threshold": 2,
    "connect_timeout_s": 3,
    "upstream_timeout_s": 30,
    "access_log": "logs/lb_access.csv",
}


class Backend:
    """One upstream server plus its live health/traffic bookkeeping."""

    def __init__(self, cfg):
        self.id = cfg["id"]
        self.host = cfg["host"]
        self.port = int(cfg["port"])
        self.weight = int(cfg.get("weight", 1))
        self.healthy = True             # optimistic until the first check
        self.consec_fail = 0
        self.consec_ok = 0
        self.in_flight = 0
        self.requests = 0
        self.errors = 0
        self.latencies = deque(maxlen=5000)   # upstream ms, newest last
        self.current_weight = 0         # smooth-WRR state
        self.pool = deque()             # idle keep-alive sockets to this backend
        self.lock = threading.Lock()

    def addr(self):
        return (self.host, self.port)

    def snapshot(self):
        lat = sorted(self.latencies)
        pct = lambda p: round(lat[min(len(lat) - 1, int(p / 100 * len(lat)))], 1) if lat else 0
        return {
            "id": self.id, "host": self.host, "port": self.port,
            "weight": self.weight, "healthy": self.healthy,
            "in_flight": self.in_flight, "requests": self.requests,
            "errors": self.errors,
            "latency_ms": {"p50": pct(50), "p95": pct(95), "p99": pct(99)},
        }


class LB:
    def __init__(self):
        self.cfg = dict(DEFAULTS)
        self.backends = []
        self.rr_index = 0
        self.lock = threading.Lock()
        self.started = time.time()
        self.total_requests = 0
        self.total_errors = 0
        self.log_lock = threading.Lock()
        self.log_fh = None
        self.reload()

    # -- config ---------------------------------------------------------------
    def reload(self):
        with open(CONF_PATH) as fh:
            file_cfg = json.load(fh)
        cfg = dict(DEFAULTS)
        cfg.update(file_cfg)
        with self.lock:
            old = {b.id: b for b in self.backends}
            fresh = []
            for bc in cfg["backends"]:
                if bc["id"] in old:            # keep live stats across reloads
                    b = old[bc["id"]]
                    b.host, b.port = bc["host"], int(bc["port"])
                    b.weight = int(bc.get("weight", 1))
                    fresh.append(b)
                else:
                    fresh.append(Backend(bc))
            self.backends = fresh
            self.cfg = cfg
        log_path = cfg["access_log"]
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        new_log = not os.path.exists(log_path)
        if self.log_fh:
            self.log_fh.close()
        self.log_fh = open(log_path, "a", buffering=1)
        if new_log:
            self.log_fh.write("ts,client,method,path,backend,upstream_ms,status,bytes\n")
        print(f"[lb] config loaded: {cfg['algorithm']}, "
              f"{len(self.backends)} backend(s): {[b.id for b in self.backends]}")

    # -- backend selection ----------------------------------------------------
    def healthy_backends(self):
        return [b for b in self.backends if b.healthy]

    def pick(self, client_ip, exclude=()):
        """Choose a backend for this request using the configured algorithm."""
        pool = [b for b in self.healthy_backends() if b.id not in exclude]
        if not pool:
            return None
        algo = self.cfg["algorithm"]
        with self.lock:
            if algo == "least_connections":
                return min(pool, key=lambda b: (b.in_flight, b.requests))
            if algo == "ip_hash":
                return pool[hash(client_ip) % len(pool)]
            if algo == "weighted_round_robin":
                # Smooth WRR (nginx algorithm): pick highest current_weight,
                # then subtract the total — spreads weights evenly over time.
                total = sum(b.weight for b in pool)
                for b in pool:
                    b.current_weight += b.weight
                chosen = max(pool, key=lambda b: b.current_weight)
                chosen.current_weight -= total
                return chosen
            # default: round_robin
            self.rr_index = (self.rr_index + 1) % len(pool)
            return pool[self.rr_index]

    # -- access log -----------------------------------------------------------
    def log(self, client, method, path, backend_id, ms, status, nbytes):
        with self.log_lock:
            self.log_fh.write(f"{time.time():.3f},{client},{method},{path},"
                              f"{backend_id},{ms:.1f},{status},{nbytes}\n")


LB_STATE = LB()

# ───────────────────────────── health checking ──────────────────────────────

def health_loop():
    """Actively poll every backend's /health; eject/re-admit with hysteresis."""
    while True:
        cfg = LB_STATE.cfg
        for b in list(LB_STATE.backends):
            ok = False
            try:
                with socket.create_connection(b.addr(), timeout=cfg["health_timeout_s"]) as s:
                    s.sendall(b"GET /health HTTP/1.1\r\nHost: lb-health\r\n"
                              b"Connection: close\r\n\r\n")
                    s.settimeout(cfg["health_timeout_s"])
                    first = s.recv(1024)
                    ok = first.startswith(b"HTTP/1.1 200") or first.startswith(b"HTTP/1.0 200")
            except OSError:
                ok = False
            if ok:
                b.consec_ok += 1
                b.consec_fail = 0
                if not b.healthy and b.consec_ok >= cfg["rise_threshold"]:
                    b.healthy = True
                    print(f"[lb] backend {b.id} re-admitted")
            else:
                b.consec_fail += 1
                b.consec_ok = 0
                if b.healthy and b.consec_fail >= cfg["fail_threshold"]:
                    b.healthy = False
                    print(f"[lb] backend {b.id} EJECTED (health check failed)")
        time.sleep(cfg["health_interval_s"])


def eject_now(b):
    """Passive check: a live proxy attempt failed — eject immediately."""
    if b.healthy:
        b.healthy = False
        b.consec_fail = LB_STATE.cfg["fail_threshold"]
        b.consec_ok = 0
        print(f"[lb] backend {b.id} EJECTED (passive: connect/proxy failure)")


# ───────────────────────────── HTTP plumbing ────────────────────────────────

HOP_BY_HOP = {b"connection", b"keep-alive", b"proxy-authenticate",
              b"proxy-authorization", b"te", b"trailers",
              b"transfer-encoding", b"upgrade"}


def read_head(sock_file):
    """Read one HTTP message head. Returns (first_line, headers_list, dict)."""
    first = sock_file.readline(65536)
    if not first or first in (b"\r\n", b"\n"):
        return None, None, None
    headers = []
    hmap = {}
    while True:
        line = sock_file.readline(65536)
        if line in (b"\r\n", b"\n", b""):
            break
        headers.append(line)
        k, _, v = line.partition(b":")
        hmap[k.strip().lower()] = v.strip()
    return first.rstrip(b"\r\n"), headers, hmap


def get_upstream(backend, timeout):
    """Reuse a pooled keep-alive socket if one is idle, else connect fresh."""
    with backend.lock:
        while backend.pool:
            s = backend.pool.popleft()
            # A readable idle socket means EOF or stray bytes — throw it away.
            s.setblocking(False)
            try:
                if s.recv(1, socket.MSG_PEEK):
                    s.close()
                    continue
                s.close()          # got EOF
                continue
            except BlockingIOError:
                s.setblocking(True)
                s.settimeout(timeout)
                return s, True
            except OSError:
                try:
                    s.close()
                except OSError:
                    pass
    s = socket.create_connection(backend.addr(),
                                 timeout=LB_STATE.cfg["connect_timeout_s"])
    s.settimeout(timeout)
    return s, False


def pump(src, dst):
    """Copy bytes one way until EOF/error. Used for WebSocket tunnelling."""
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def build_upstream_head(first, headers, hmap, client_ip, is_ws):
    """Rewrite the request head with proper proxy headers."""
    out = [first + b"\r\n"]
    for line in headers:
        k = line.split(b":", 1)[0].strip().lower()
        if k in HOP_BY_HOP or k in (b"x-forwarded-for", b"x-real-ip",
                                    b"x-forwarded-proto"):
            continue
        out.append(line)
    prior = hmap.get(b"x-forwarded-for")
    xff = (prior + b", " if prior else b"") + client_ip.encode()
    out.append(b"X-Forwarded-For: " + xff + b"\r\n")
    out.append(b"X-Real-IP: " + client_ip.encode() + b"\r\n")
    out.append(b"X-Forwarded-Proto: http\r\n")
    if is_ws:
        out.append(b"Connection: Upgrade\r\nUpgrade: websocket\r\n")
    else:
        out.append(b"Connection: keep-alive\r\n")
    out.append(b"\r\n")
    return b"".join(out)


# ───────────────────────────── request handling ─────────────────────────────

def handle_client(client, client_addr):
    """One accepted TCP connection: serve requests until it closes."""
    client_ip = client_addr[0]
    client.settimeout(60)
    cf = client.makefile("rb")
    try:
        while True:
            first, headers, hmap = read_head(cf)
            if first is None:
                return
            try:
                method, path, _version = first.split(b" ", 2)
            except ValueError:
                return
            LB_STATE.total_requests += 1

            # ---- LB admin endpoints, served by the LB itself --------------
            if path.startswith(b"/lb/") or path == b"/lb":
                if not serve_admin(client, method, path):
                    return
                continue

            # ---- request body (Content-Length only; our clients comply) ---
            body = b""
            clen = int(hmap.get(b"content-length", b"0") or 0)
            if clen:
                body = cf.read(clen)

            is_ws = (b"upgrade" in hmap.get(b"connection", b"").lower()
                     and hmap.get(b"upgrade", b"").lower() == b"websocket")

            # ---- pick a backend, retry on connect failure -----------------
            tried = set()
            upstream = pooled = backend = None
            while True:
                # WS must stick to one backend for its whole lifetime.
                backend = LB_STATE.pick(client_ip, exclude=tried) if not is_ws \
                    else LB_STATE.pick_sticky(client_ip, tried)
                if backend is None:
                    send_error(client, 503, "No healthy backends")
                    LB_STATE.total_errors += 1
                    LB_STATE.log(client_ip, method.decode(), path.decode(),
                                 "-", 0.0, 503, 0)
                    return
                try:
                    upstream, pooled = get_upstream(
                        backend, LB_STATE.cfg["upstream_timeout_s"])
                    break
                except OSError:
                    tried.add(backend.id)
                    eject_now(backend)      # passive ejection + safe retry:
                    continue                # nothing was sent upstream yet

            head = build_upstream_head(first, headers, hmap, client_ip, is_ws)
            backend.in_flight += 1
            backend.requests += 1
            t0 = time.time()
            try:
                upstream.sendall(head + body)

                if is_ws:
                    # Tunnel: hand the two sockets to each other and step aside.
                    threading.Thread(target=pump, args=(client, upstream),
                                     daemon=True).start()
                    pump(upstream, client)
                    ms = (time.time() - t0) * 1000
                    LB_STATE.log(client_ip, "WS", path.decode(), backend.id,
                                 ms, 101, 0)
                    return

                uf = upstream.makefile("rb")
                rfirst, rheaders, rhmap = read_head(uf)
                if rfirst is None:
                    raise OSError("upstream sent no response")
                status = int(rfirst.split(b" ")[1])
                r_clen = rhmap.get(b"content-length")
                keep_up = rhmap.get(b"connection", b"keep-alive")\
                    .lower() != b"close" and r_clen is not None

                # Response head to the client (client stays keep-alive).
                out = [rfirst + b"\r\n"]
                for line in rheaders:
                    k = line.split(b":", 1)[0].strip().lower()
                    if k == b"connection":
                        continue
                    out.append(line)
                out.append(b"Connection: keep-alive\r\n" if r_clen is not None
                           else b"Connection: close\r\n")
                out.append(b"\r\n")
                client.sendall(b"".join(out))

                nbytes = 0
                if r_clen is not None:            # exact-length body
                    remaining = int(r_clen)
                    while remaining:
                        chunk = uf.read(min(65536, remaining))
                        if not chunk:
                            raise OSError("upstream truncated body")
                        client.sendall(chunk)
                        nbytes += len(chunk)
                        remaining -= len(chunk)
                else:                             # stream until upstream EOF
                    while True:
                        chunk = uf.read1(65536)
                        if not chunk:
                            break
                        client.sendall(chunk)
                        nbytes += len(chunk)

                ms = (time.time() - t0) * 1000
                backend.latencies.append(ms)
                if status >= 500:
                    backend.errors += 1
                LB_STATE.log(client_ip, method.decode(), path.decode(),
                             backend.id, ms, status, nbytes)

                if keep_up:                       # return socket to the pool
                    with backend.lock:
                        upstream.settimeout(LB_STATE.cfg["upstream_timeout_s"])
                        backend.pool.append(upstream)
                else:
                    upstream.close()
                if r_clen is None:
                    return                        # we promised Connection: close
            except OSError:
                backend.errors += 1
                LB_STATE.total_errors += 1
                eject_now(backend)
                try:
                    upstream.close()
                except OSError:
                    pass
                ms = (time.time() - t0) * 1000
                LB_STATE.log(client_ip, method.decode(), path.decode(),
                             backend.id, ms, 502, 0)
                send_error(client, 502, "Upstream failed mid-request")
                return
            finally:
                backend.in_flight -= 1
    except OSError:
        pass
    finally:
        try:
            cf.close()
            client.close()
        except OSError:
            pass


def pick_sticky(self, client_ip, tried):
    """WebSocket connections always use ip_hash so reconnects re-pin."""
    pool = [b for b in self.healthy_backends() if b.id not in tried]
    if not pool:
        return None
    return pool[hash(client_ip) % len(pool)]


LB.pick_sticky = pick_sticky


# ───────────────────────────── admin endpoints ──────────────────────────────

def stats_json():
    lb = LB_STATE
    return json.dumps({
        "algorithm": lb.cfg["algorithm"],
        "uptime_s": round(time.time() - lb.started, 1),
        "total_requests": lb.total_requests,
        "total_errors": lb.total_errors,
        "backends": [b.snapshot() for b in lb.backends],
    }, indent=2)


DASHBOARD = """<!doctype html><meta charset=utf-8>
<meta http-equiv=refresh content=2>
<title>LB dashboard</title>
<style>
 body{font:14px -apple-system,Segoe UI,Roboto,sans-serif;margin:40px auto;max-width:760px;color:#1a1a1e}
 h1{font-size:20px} table{border-collapse:collapse;width:100%%}
 td,th{border:1px solid #ddd;padding:8px 10px;text-align:left;font-variant-numeric:tabular-nums}
 th{background:#f4f4f6}.up{color:#2e7d32;font-weight:600}.down{color:#c62828;font-weight:600}
 .muted{color:#777}
</style>
<h1>Load balancer — sys1:3269</h1>
<p class=muted>algorithm <b>%(algo)s</b> · uptime %(up).0fs · %(tot)d requests · %(err)d errors · auto-refresh 2s</p>
<table><tr><th>backend</th><th>addr</th><th>health</th><th>in-flight</th>
<th>requests</th><th>errors</th><th>p50 ms</th><th>p95 ms</th><th>p99 ms</th></tr>%(rows)s</table>
<p class=muted>JSON: <a href=/lb/stats>/lb/stats</a> · reload config: POST /lb/reload</p>"""


def serve_admin(client, method, path):
    """Handle /lb/* requests. Returns False to close the connection."""
    if path == b"/lb/stats":
        body = stats_json().encode()
        ctype = b"application/json"
    elif path in (b"/lb", b"/lb/"):
        rows = ""
        for b in LB_STATE.backends:
            s = b.snapshot()
            rows += ("<tr><td>%s</td><td>%s:%d</td>"
                     "<td class=%s>%s</td><td>%d</td><td>%d</td><td>%d</td>"
                     "<td>%.1f</td><td>%.1f</td><td>%.1f</td></tr>" % (
                         s["id"], s["host"], s["port"],
                         "up" if s["healthy"] else "down",
                         "UP" if s["healthy"] else "DOWN",
                         s["in_flight"], s["requests"], s["errors"],
                         s["latency_ms"]["p50"], s["latency_ms"]["p95"],
                         s["latency_ms"]["p99"]))
        body = (DASHBOARD % {"algo": LB_STATE.cfg["algorithm"],
                             "up": time.time() - LB_STATE.started,
                             "tot": LB_STATE.total_requests,
                             "err": LB_STATE.total_errors,
                             "rows": rows}).encode()
        ctype = b"text/html; charset=utf-8"
    elif path == b"/lb/reload" and method == b"POST":
        try:
            LB_STATE.reload()
            body, ctype = b'{"ok":true}', b"application/json"
        except Exception as e:                       # bad config must not kill the LB
            body = json.dumps({"ok": False, "error": str(e)}).encode()
            ctype = b"application/json"
    elif path == b"/lb/health":
        body, ctype = b'{"status":"ok","service":"lb"}', b"application/json"
    else:
        body, ctype = b'{"error":"no such admin route"}', b"application/json"
    client.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: " + ctype +
                   b"\r\nContent-Length: " + str(len(body)).encode() +
                   b"\r\nConnection: keep-alive\r\n\r\n" + body)
    return True


def send_error(client, code, msg):
    body = json.dumps({"error": msg}).encode()
    try:
        client.sendall(b"HTTP/1.1 " + str(code).encode() + b" LB Error\r\n"
                       b"Content-Type: application/json\r\nContent-Length: " +
                       str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body)
    except OSError:
        pass


# ───────────────────────────── main ─────────────────────────────────────────

def main():
    signal.signal(signal.SIGHUP, lambda *_: LB_STATE.reload())
    threading.Thread(target=health_loop, daemon=True).start()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((LB_STATE.cfg["listen_host"], LB_STATE.cfg["listen_port"]))
    srv.listen(512)
    print(f"[lb] listening on {LB_STATE.cfg['listen_host']}:"
          f"{LB_STATE.cfg['listen_port']} — dashboard at /lb/")
    while True:
        client, addr = srv.accept()
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        threading.Thread(target=handle_client, args=(client, addr),
                         daemon=True).start()


if __name__ == "__main__":
    main()
