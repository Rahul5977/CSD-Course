# Demonstration script — 7 minutes

Pre-flight (5 min before): `make up && make seed`; open http://localhost:3000, http://localhost:8000/docs
and http://localhost:3001 in three tabs; keep `docs/media/chaos-test.gif` open as the backup.
Never depend on a live external API during the demo: the rainfall record is cached, the land
cover and water mask are stored per village by `make seed`'s follow-up suitability run.

| # | Time | Show | Say |
|---|---|---|---|
| 1 | 0:30 | Landing page at `/` — scroll past the hero to *Nothing is a black box*; click *Open the planner* | "The system takes only a contour map. Everything you will see is derived from that file — the UTM zone, the grid, the source accuracy, the pour point. Every algorithm on this page is named and cited." |
| 2 | 0:45 | Upload `contours_1m.kml`; progress stages; village appears as *Khapri*; contours + streams draw | "Parse → TIN → Priority-Flood → D8. The streams are the modelled network at 5 ha; compare with the river in the imagery. The village name came from reverse-geocoding the centroid." |
| 3 | 1:00 | Suggested sites panel; hover the criterion bars; *How sites are ranked* | "Four terrain criteria — an upstream-area plateau, a slope plateau, wetness, impoundment efficiency — AHP-weighted, consistency ratio 0.004. Not a black box: every site shows its scores." |
| 4 | 0:45 | Click site #1 → catchment polygon, snapped outlet, snap distance | "38 ha, ±26 %. Validated against pysheds within 2–3 % on the main outlets; the sensitivity plot in the report shows why snapping matters." |
| 5 | 1:15 | Rainfall card → *Design a pond at the outlet* → dimensions, EAV curve, methods table, reliability | "45 years of ERA5-Land; the 75 % dependable year is 1 168 mm. Three runoff methods disagree by 188 % — that range is information. The depth is chosen by cost; it fills in 25 of 25 years." |
| 6 | 0:45 | *Assess land & rank sites* (pre-run) → eligible patches, constraint list, ownership unknown | "Seven named constraints; ownership is 'unknown' because no cadastral layer was supplied — never assumed government." |
| 7 | 0:45 | Log in as planner → save → submit; log in as officer → approve → audit trail → *Export PDF* | "State machine plus roles; every move is an append-only audit row. The PDF attaches to an MGNREGA proposal." |
| 8 | 0:45 | `docker stop pond-planner-api-1`; reload; offline badge, results still there; `docker start …` | "Village internet is 2G and intermittent. Cached results with a staleness badge." |
| 9 | 0:30 | Grafana dashboard; Swagger | "Two worker bulkheads, Prometheus metrics, 40 documented operations with an error catalogue." |

Questions to expect: why D8 (ADR 0009) · why the area plateau (ADR 0014) · why SCS-CN daily
(ADR 0010) · why not ML (ADR 0017) · what the ±20 % means (DEM is 30 m-derived) · why no
GRASS (ADR 0015) · why FastAPI/PostGIS over Flask/Mongo (ADR 0005, 0006).
