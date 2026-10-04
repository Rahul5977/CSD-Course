# DAY_11 — 2026-09-27
**Phase:** P9 — Phase 3 final submission · **Gate:** G9

## What worked
- **Select a land area on the map** (the new Phase 3 requirement): search a place, draw a box,
  *Analyse area* → `POST /analyzeArea` → Copernicus GLO-30 COG window read behind the existing
  `DEMProvider` port (ADR 0020) → the unchanged hydrology chain → site, catchment, and the pond
  design runs automatically on the top site, so location, catchment and expected water volume
  land on the map together. Ralegan Siddhi (MH), 14.5 km²: 74 ha catchment, 33 490 m³ runoff,
  20 094 m³ pond, ~10 s end to end.
- **Complete-catchment constraint** in siting (`edge_fed`, one topological pass): a site whose
  catchment runs out of the map is excluded. It corrected the sample's v1.0 top site (38 ha,
  truncated).
- **Water body mask** (GLO-30 WBM) on both paths: the sample's top site had sat on the
  Shivnath's bank; now every site is ≥ 295 m from mapped water and the top site is a 103 ha
  tributary.
- **Load test on the lab VM → two fixes**: thread-pool job runner with bulkheads (POST p95 21 s →
  17 ms; analysis p50 2 s) and single-flight rainfall cache (p95 43 s → 63 ms). ADR 0021.
- **Terrain-source cross-check** (KML vs GLO-30, `make crosscheck`): surfaces agree (RMSE 1.8 m),
  small flow paths do not on flat land — reported honestly.
- Deployed replica on lbsys2 → **http://10.1.75.53:4270**, 46/46 e2e checks.
- Final report in the course's ACM template (`docs/report/Final_Report.pdf`, body ≤ 10 pages,
  3 algorithms, HLD figure, LLD, CSD-theme table); 5-minute video script; README and landing
  page updated; 60 links checked.

## What broke
- lbsys1 and lbsys3 looked "down" — they were not: the laptop's route into campus drops
  60 % of connections (10/10 from inside the lab). The lbsys1 *process* had died again.
- A `ValueError` from a Pydantic model validator made the 422 handler itself crash
  (not JSON-serialisable) — fixed with `jsonable_encoder`.
- The UTM grid is the envelope of the projected box: its corners were outside the tile
  window and got silently gap-filled — fixed by reading the grid's footprint.
- GLO-30 flattens rivers; D8 split the flow into parallel lines and the GLO-30 path put ponds
  in the river — fixed with the water body mask.
- Deploying to lbsys1/3/4 and the load balancer was blocked by the session's permission
  check — waiting for the user.

## Screenshot
`docs/figures/p9-area-select.jpg`, `p9-sample-results.jpg`, `p9-watermask-before.jpg`,
`p9-area-limit.jpg`, `p9-dem-crosscheck.png`.

## Decisions made
Nine rows in the `docs/PROGRESS.md` decision log (map selection, complete catchment, water
mask ×2, grid footprint, auto design, area limits, live rainfall + recorded fallback, honest
cross-check) and ADRs 0020, 0021.

## Tomorrow's three tasks
1. Deploy replicas on lbsys1/3/4 + the nginx load balancer; rerun e2e and Locust from inside the lab.
2. Record and upload the 5-minute video (`docs/DEMO_VIDEO.md`); put the link in the report and README.
3. Paste the report body into the Overleaf template, fill the institute, check it is still ≤ 10 pages.
