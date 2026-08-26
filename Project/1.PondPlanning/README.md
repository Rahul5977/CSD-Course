# AI-based Village Pond Planning System

[![CI](https://github.com/Rahul5977/AI-BasedPondAnalysis/actions/workflows/ci.yml/badge.svg)](https://github.com/Rahul5977/AI-BasedPondAnalysis/actions/workflows/ci.yml)

Upload a contour map (KML/KMZ) of a village and get, from the browser: the terrain
(DEM, hillshade, slope, curvature, wetness), the modelled streams, ranked pond
sites with the reasoning, the catchment of any point you click, 45 years of rainfall
statistics, runoff by three methods, a costed pond design with fill reliability,
eligible land under named constraints, and a recommendation you can approve and
export. Every number carries its unit and an uncertainty band. Nothing about any one
map is hard-coded — the UTM zone, grid resolution, source accuracy and pour point are
all derived from the upload.

7th-semester assignment · full specification in `docs/assignment/`, execution plan in
`docs/PLAN.md`, technical report in `docs/report/REPORT.md`, API cookbook in
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
| `make check` (dev install) | ruff, mypy `--strict`, 202 tests (+1 skipped without the sample), no Docker needed |

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
| `make check` fails on a fresh clone with a network error | Nothing should — tests use recorded fixtures | Check `POND_RAINFALL_SOURCE` is unset in your shell (tests force `recorded`) |

### Public URL for the Phase 2 route

`make tunnel` runs `ngrok http 3000` and prints the public URL; `POST <url>/api/v1/analyzeContour`
then accepts the KML/KMZ upload from anywhere. The tunnel lives as long as the command runs.

## Documentation map

- `docs/report/REPORT.md` — the technical report (methodology, algorithms, validation, results)
- `docs/api/cookbook.md`, `docs/api/errors.md`, `docs/api/openapi.json` — the API
- `docs/adr/` — 19 architecture decision records
- `docs/PROGRESS.md` — decision log and session history; `docs/progress/DAY_NN.md` — daily logs
- `docs/LICENSES.md` — data-source licence register
- `docs/DEMO.md` — the 7-minute demonstration script
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
