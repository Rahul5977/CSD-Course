# AI-based Village Pond Planning System

[![CI](https://github.com/Rahul5977/AI-BasedPondAnalysis/actions/workflows/ci.yml/badge.svg)](https://github.com/Rahul5977/AI-BasedPondAnalysis/actions/workflows/ci.yml)

**Draw a box around a village's land on the satellite map** — or upload a contour map
(KML/KMZ) — and get, from the browser: the suggested pond location, the catchment draining to
it and the expected water volume, all overlaid on the map; and behind them the terrain
(DEM, hillshade, slope, curvature, wetness), the modelled streams, ranked pond
sites with the reasoning, the catchment of any point you click, 45 years of rainfall
statistics, runoff by three methods, a costed pond design with fill reliability,
eligible land under named constraints, and a recommendation you can approve and
export. Every number carries its unit and an uncertainty band. Nothing about any one
map is hard-coded — the UTM zone, grid resolution, source accuracy and pour point are
all derived from the selection or the upload.

| Submission item | Where |
|---|---|
| Final report (ACM template, ≤ 10 pages + appendix) | [`docs/report/Final_Report.pdf`](docs/report/Final_Report.pdf) · source `docs/report/latex/` (`make report-latex`) |
| Working front-end | **http://10.1.75.53:4272** (nginx load balancer over four lab replicas, campus network) · planner at `/app`, API docs at `/docs` · replicas :4269, :4270, :4271 |
| Repository | https://github.com/Rahul5977/AI-BasedPondAnalysis |
| Demo video (≤ 5 min) | script in [`docs/DEMO_VIDEO.md`](docs/DEMO_VIDEO.md) · YouTube link: *added after upload* |

7th-semester assignment · full specification in `docs/assignment/`, execution plan in
`docs/PLAN.md`, final report in `docs/report/Final_Report.pdf`, API cookbook in
`docs/api/cookbook.md`.

## Installation

### Prerequisites

| Tool | Version | Check |
|---|---|---|
| Docker Desktop (or Engine + Compose v2) | ≥ 24 / Compose ≥ 2.20 | `docker compose version` |
| GNU make | any | `make --version` |
| curl, python3 | any (used by `make seed`) | `curl --version` |
| For development only: `uv` ≥ 0.4 and Node ≥ 20 | | `uv --version`, `node --version` |

RAM: 4 GB for the stack. Disk: ~3 GB of images. Ports used: 3000 (app), 8000 (API),
3001 (Grafana), 9090 (Prometheus), 8080 (TiTiler), 9000/9001 (MinIO), 5432, 6379.
Apple Silicon: TiTiler runs under amd64 emulation automatically.

### Run it

```bash
git clone https://github.com/Rahul5977/AI-BasedPondAnalysis.git
cd AI-BasedPondAnalysis
cp .env.example .env          # optional: change ports or passwords
make up                        # builds the images, starts 11 services, applies migrations
make seed                      # analyses the provided sample map end to end (~10 s)
```

Then open **http://localhost:3000**, pick the village that appeared (the sample map
resolves to *Khapri, Durg district, Chhattisgarh*), click on the map for a catchment,
and press *Design a pond at the outlet*.

### Verify

| Check | Expected |
|---|---|
| `curl -s localhost:8000/health` | `{"status":"ok", …}` |
| `curl -s localhost:8000/ready` | `"status":"ready"` with postgres, redis and object_store reachable |
| `curl -s localhost:8000/api/v1/meta/implementation-status` | `"fixture_backed": []` — every route is real |
| `docker compose -f infra/docker-compose.yml ps` | 11 services, `healthy` where a healthcheck exists |
| http://localhost:8000/docs | Swagger UI, 40+ operations |
| http://localhost:3001 | Grafana, dashboard *Pond Planner* (anonymous viewer) |
| `make check` (dev install) | ruff, mypy `--strict`, 205 tests (+1 skipped without the sample), no Docker needed |

Demo users (`POND_USERS` in `.env`): `viewer/viewer-demo`, `planner/planner-demo`,
`officer/officer-demo`. Only a planner can save a recommendation; only an officer can approve.

### Everyday commands

```bash
make help        # every target with a one-line purpose
make logs        # tail every service
make down        # stop (ARGS=-v also drops the volumes → next make up starts clean)
make check       # lint + types + tests (also what CI runs)
make figures     # regenerate the evidence figures from the sample map
make loadtest    # Locust, 50 users for 60 s, against the running stack
make tunnel      # expose the app on a public URL through ngrok (needs an ngrok account)
make api-dev     # API alone, no Docker: in-memory persistence, inline jobs, local store
make web-dev     # Vite dev server for the frontend, proxying /api and /tiles
```

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `make up` fails with *port is already allocated* | Something else on 3000/8000/5432/6379/9000 | Set `POND_WEB_PORT`, `POND_API_PORT`, … in `.env` |
| `ImportError: libexpat.so.1` in the API container | rasterio's wheel needs libexpat on `python:slim` | Already in `infra/Dockerfile.api`; rebuild with `make up` after pulling |
| `no matching manifest for linux/arm64` for TiTiler | TiTiler publishes amd64 images only | Already pinned with `platform: linux/amd64`; enable Rosetta/QEMU in Docker Desktop |
| Map tiles for a layer take ~15 s the first time | TiTiler under emulation opening a new COG | Wait once; later tiles are cached |
| `make seed` prints `queued 0` forever | Workers not up yet, or Redis unreachable | `make ps`; `make logs` on `worker-heavy`; `docker compose … up -d --remove-orphans` |
| Upload returns `422 elevation_not_found` | The KML has no elevation in Z, a whitelisted `ExtendedData` field, or the placemark name | Check the parser rules in `docs/adr/0011-contour-kml-adapter.md`; `ID` fields are deliberately rejected |
| Upload returns `422 unsupported_input` | Not a `.kml`/`.kmz`, or no `LineString` placemarks | Export contours as lines, not points |
| Pond design confidence is `low`, warning `soil_assumed` | SoilGrids (ISRIC) timed out — it can take 40 s | Retry later; the default hydrologic soil group C is stated in the result |
| Suitability job is slow (60–90 s) | Sentinel-2 scenes are read live from AWS for the NDWI mask | Expected; the water mask and land parcels are then stored per village |
| `429 queue_saturated` on an analysis POST | More than `POND_MAX_QUEUE_DEPTH` jobs waiting | Wait `Retry-After` seconds, or raise the limit |
| `403 forbidden` on save/approve | Logged in with an insufficient role | Log in as `planner` to save, `officer` to approve |
| Grafana panels say *No data* | Fewer than two scrapes yet, or no jobs run | Run `make seed` or click the map; wait 30 s |
| First `make up` on a fresh volume: `alembic` says *connection refused* | Postgres's initdb restarts the server once; the healthcheck now probes TCP and `make up` retries the migration | Run `make up` again if it still fails on a slow disk |
| `beat` restarts with *Permission denied: 'celerybeat-schedule'* | The image runs unprivileged; the schedule file is written to `/tmp` | Pull and `make up` (rebuilds the compose command) |
| An old `worker` container lingers after upgrading | The single worker was split into two bulkheads | `docker compose -f infra/docker-compose.yml up -d --remove-orphans` |
| `make up` build fails with *failed to fetch anonymous token … connection reset* | The network resets Docker Hub connections (seen on the campus network) | The `# syntax=` pins were removed so cached builds work; retry `make up` — the resets are intermittent |
| `uv run mypy` (or pytest) fails with *Failed to spawn* / *bad interpreter* after moving the project folder | The venv's script shebangs still point at the old path | `rm -rf .venv && make install` |
| `make e2e` fails only at `/ready` on a no-Docker deployment | Old images probed postgres/redis unconditionally | Fixed: `/ready` now probes only the configured adapters; pull and restart |
| `make check` fails on a fresh clone with a network error | Nothing should — tests use recorded fixtures | Check `POND_RAINFALL_SOURCE` is unset in your shell (tests force `recorded`) |
| *Analyse area* stays disabled, *Select between 0.25 and 25 km²* | The drawn box is too small or too large (the API answers `422 area_out_of_range`) | Zoom to the village and redraw; 25 km² is the per-request stress limit |
| `503 upstream_unavailable` from `/analyzeArea` | The Copernicus GLO-30 bucket on AWS was unreachable | Check outbound HTTPS; the contour-upload route works offline |
| Result warning `no_complete_catchment` | Every candidate's catchment runs out of the selected box | Redraw a larger box that includes the land upslope of the site |
| Lab URL times out from a laptop but works from another lab VM | Packet loss on the laptop's route into the campus network (measured 4/10 connects from a laptop, 10/10 inside the lab) | Use the campus wired network; the e2e client retries connects |
| Lab replica died / URL returns nothing | No supervisor on the VMs | `infra/lab/run_replica.sh` restarts uvicorn in a loop; start it with `ssh -f <vm> 'cd ~/pond/app && PORT=4000 exec setsid infra/lab/run_replica.sh >> ~/pond/server.log 2>&1 < /dev/null'` |

### Deployment on the four lab machines (no Docker)

The lab VMs are unprivileged containers, so each replica is one process (`infra/lab/run_replica.sh`:
API + built SPA, in-memory persistence, thread-pool job runner with bulkheads, local store, live
rainfall) and a user-space nginx (`infra/lab/nginx-lb.conf`, `ip_hash` + passive health checks)
balances the replicas. Copy the tree, `uv sync --no-dev --frozen`, run the script; `make e2e
BASE=http://10.1.75.53:4272` verifies it through the load balancer (46/46).

### Public URL for the Phase 2 route

`make tunnel` runs `ngrok http 3000` and prints the public URL; `POST <url>/api/v1/analyzeContour`
then accepts the KML/KMZ upload from anywhere. The tunnel lives as long as the command runs.

## Documentation map

- `docs/report/Final_Report.pdf` — the submitted report (source `docs/report/latex/`); `docs/report/REPORT.md` — extended v1.0 report
- `docs/api/cookbook.md`, `docs/api/errors.md`, `docs/api/openapi.json` — the API
- `docs/adr/` — 21 architecture decision records (0020: map-selected area; 0021: lab replicas and bulkheads)
- `docs/PROGRESS.md` — decision log and session history; `docs/progress/DAY_NN.md` — daily logs
- `docs/LICENSES.md` — data-source licence register
- `docs/DEMO_VIDEO.md` — the 5-minute video script (Phase 3); `docs/DEMO.md` — the 7-minute live demo
- `docs/design/BRIEF.md`, `web/design/` — the design brief, tokens, components and prototypes (push to the AI design tool with the design-sync tooling)

## Development

```bash
make install     # uv venv + all dependencies (Python 3.12)
make check       # ruff format --check · ruff check · mypy --strict (domain, engines) · pytest
make test-cov    # coverage report in htmlcov/
cd web && npm ci && npm run dev
```

The architecture is layered (`docs/adr/0001-layered-architecture.md`) and enforced by
`tests/test_layering.py`; `domain/` and `engines/` import no framework. AI tools (the assistant
Code) were used during development for drafting, refactoring and documentation, as the
assignment's policy permits; every design decision, algorithm and library is explained in
the ADRs and the report and can be defended live.
