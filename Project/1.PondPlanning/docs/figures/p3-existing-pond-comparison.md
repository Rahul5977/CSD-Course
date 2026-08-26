# Existing-pond comparison — evidence register row 17

**Method.** OpenStreetMap (Overpass, 2026-08-26) lists six water polygons inside the
sample map's extent: the Sivnath river and five tanks. The three tanks fully inside
the analysed grid were fed to `POST /analysis/pond-design` at their centroids, with
live providers (Open-Meteo, WorldCover; SoilGrids timed out → HSG C assumed).

| Tank (OSM way) | Mapped area | Implied capacity at 2.5 m | Our catchment at the tank | 75 % dependable SCS-CN runoff | Harvestable (×0.6) | Supply / capacity | Natural impoundment at +2 m (EAV) |
|---|---|---|---|---|---|---|---|
| 135692840 | 3.36 ha | ≈ 84 000 m³ | 10.9 ha (±50 %), snapped 30 m | 15 979 m³ | 9 587 m³ | **0.11** | 39 851 m³ |
| 135692870 | 2.22 ha | ≈ 55 500 m³ | 2.0 ha (±50 %), snapped 30 m | 6 349 m³ | 3 810 m³ | **0.07** | 10 653 m³ |
| 1414810258 (basin) | 4.45 ha | — | outside the analysed extent by ~30 m | — | — | — | — |

**Reading.** Neither existing tank can be filled by the runoff of the catchment our
model delineates at it — the local supply is a tenth of the capacity. Two explanations,
both consistent with the ground: (1) Durg district is a canal command area (Tandula /
Sivnath systems); these are irrigation tanks filled by the canal network, not
rainwater-harvesting ponds — the model correctly says "local runoff will not fill
this"; (2) at 30 m cells a 2–11 ha catchment is 20–120 cells with a ±50 % band, and
the tanks sit on the flat floodplain where the DEM cannot resolve drainage, so the
true catchment may be several times larger.

**What agrees.** The natural impoundment the DEM gives at +2 m at tank 135692840
(39 851 m³) is within −40 % of the tank's implied capacity at 2 m depth (67 000 m³) —
the terrain *does* hold a pool of that order there, which is why a tank was built.

**Consequence for the design engine.** The siting score's upstream-area plateau and the
supply-side target are doing the right thing: the sites the engine ranks first (38–57 ha
upstream, fill reliability 100 %) are places rain alone can fill; the existing tanks are
places a canal fills. Both facts go in the report's validation section, including the
error. Raw output: `p3-existing-pond-comparison.json`.
