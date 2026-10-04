# ADR 0018 — Offline-first frontend: a service worker serves the last good results

**Status:** Accepted · 2026-08-26 · Phase P5

## Context

Village internet is 2G and intermittent. The P6 chaos test — disconnect the
network, reload, the app still shows results with a staleness badge — is on
the never-cut list, and the frontend is where the user sees it.

## Decision

A 60-line service worker (`web/public/sw.js`), no framework:

- tiles (Esri basemap, `/tiles/` COG tiles) and built assets: **cache-first** —
  a tile for a given URL never changes;
- `GET /api/...`: **network-first**, falling back to the last cached copy with
  an `X-From-Cache: true` header, which the app turns into an "Offline —
  showing the last saved results" badge in the header;
- the app shell: network-first with cache fallback.

POSTs are never cached: a new analysis needs the worker.

## Consequences

- The chaos test is a one-line demo: kill the network, reload, the village,
  its layers, rainfall and the last design are still there and labelled stale.
- Stale is *visible*, never silent — the same rule as the fixture header in
  P0 and the `stale_data` warning in the rainfall engine.
- Nothing in the API changes; the worker is purely client-side.

## Alternatives rejected

- A PWA framework (Workbox): more to defend for the same three rules.
- Server-side cache headers only: the browser cache is not consulted when
  the network is down; a service worker is.
