#!/usr/bin/env bash
# Same queries as Lab 7's report/terminal_captures/02_curl_local.txt, sent through nginx.
BASE="${1:-http://localhost:8088}"
for path in \
  '/health' \
  '/search/?lat=0.74&long=0.6&cat=bank&rad=0.1' \
  '/search?lat=0.5&long=0.5&cat=cafe&rad=0.12' \
  '/search/?lat=0.2&long=0.9&cat=Hospital&rad=0.2' \
  '/search/?lat=0.5&long=0.5&cat=spaceport&rad=0.1' \
  '/search/?lat=0.5&long=abc&cat=cafe&rad=0.1' \
  '/search/?lat=0.5&long=0.5&cat=cafe'; do
  echo "\$ curl -s '$BASE$path'"
  curl -s -w '   [HTTP %{http_code}]\n' "$BASE$path"
  echo
done
