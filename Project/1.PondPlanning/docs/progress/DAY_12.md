# DAY_12 — 2026-10-03
**Phase:** P9 — Phase 3 final submission · **Gate:** G9

## What worked
- Diagnosed "frontend not reachable": every lab process (4 replicas + the lbsys4 nginx LB) had
  been reaped; code on disk was current. Restarted all of them under the supervisor loop.
- Backend: `make e2e` 46/46 through the load balancer http://10.1.75.53:4272, before and after
  the fixes.
- Browser, step by step on :4272: landing → KML upload (103 ha, 5 ranked sites) → site 2 and 4
  catchments (14.3 / 64.2 ha) → pond design → suitability (27 ha eligible, AHP CR 0.004) →
  place search + box → `analyzeArea` (Patan, 299 ha, GLO-30) → layer toggles → EN/HI.

## What broke
- Job progress hung at "submitting 3 %": the WebSocket handshake was lost on the laptop's lossy
  route and fired no event. Fixed with a 4 s / 15 s watchdog that falls back to polling.
- The second catchment never appeared on the map: updates were gated on `isStyleLoaded()`,
  false whenever tiles stream, with a once-only `"load"` fallback. Fixed with the `styleReady` ref.
- Browsers kept the previous bundle after a redeploy (no `Cache-Control` on HTML). Fixed in the
  single server and the compose nginx.
- The automation tab rendered a blank map while Chrome reported it hidden (window occlusion
  pauses MapLibre's render loop) — a test-harness artefact, not an app bug.

## Screenshot
Verified live in the browser (see session 20 in docs/PROGRESS.md).

## Decisions made
- WebSocket watchdog → poll fallback; `styleReady` instead of `isStyleLoaded()`; `no-cache` HTML
  + immutable assets. All three are in the PROGRESS decision log.

## Tomorrow's three tasks
1. User clicks the recommendation flow once in the UI (sign-in → save → submit → approve → export).
2. Record the video against :4272.
3. Re-check `/health` on all four replicas before the demo.
