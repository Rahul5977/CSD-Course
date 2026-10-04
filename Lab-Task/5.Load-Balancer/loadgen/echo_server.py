#!/usr/bin/env python3
"""Trivial echo server used ONLY to calibrate the load generator: if the
generator can push >=10x the throughput we later measure against the lab,
the generator is provably not the bottleneck in those measurements."""
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BODY = b'{"ok":true,"status":"ok"}'


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _reply(self):
        if self.command == "POST":
            n = int(self.headers.get("Content-Length", 0) or 0)
            if n:
                self.rfile.read(n)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(BODY)))
        self.send_header("X-Backend-Id", "echo")
        self.end_headers()
        self.wfile.write(BODY)

    do_GET = do_POST = _reply
    def log_message(self, *a):  # silence
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 19000
    print(f"[echo] listening on 127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
