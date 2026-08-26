import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { LayerControl } from "./components/LayerControl";
import { MapView } from "./components/MapView";
import { SummaryCard } from "./components/SummaryCard";
import { UploadPanel } from "./components/UploadPanel";
import { useJob } from "./hooks/useJob";
import type { MultiPolygon, Polygon } from "geojson";
import type { LayerDescriptor, VillageOut, VillageSummary } from "./types";

type Bounds = [number, number, number, number];

/** Outer ring of a Polygon, or of the first part of a MultiPolygon (PostGIS stores the latter). */
function outerRing(geometry: Polygon | MultiPolygon | null): number[][] | null {
  if (!geometry) return null;
  return geometry.type === "Polygon" ? geometry.coordinates[0] : geometry.coordinates[0]?.[0] ?? null;
}

export default function App() {
  const [villages, setVillages] = useState<VillageOut[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [summary, setSummary] = useState<VillageSummary | null>(null);
  const [layers, setLayers] = useState<LayerDescriptor[]>([]);
  const [boundary, setBoundary] = useState<Polygon | MultiPolygon | null>(null);
  const [bounds, setBounds] = useState<Bounds | null>(null);
  const [visible, setVisible] = useState<Record<string, boolean>>({ satellite: true, hillshade: true, dem: false, boundary: true });
  const [jobId, setJobId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const job = useJob(jobId);

  const refreshVillages = useCallback(async () => {
    const page = await api.villages();
    setVillages(page.items);
    return page.items;
  }, []);

  useEffect(() => {
    refreshVillages().catch((e) => setLoadError((e as Error).message));
  }, [refreshVillages]);

  // When the upload job finishes, select the village it created.
  useEffect(() => {
    if (job?.status !== "succeeded" || !jobId) return;
    api.terrainResult(jobId).then(async (result) => {
      await refreshVillages();
      setSelected(result.village_id);
    });
  }, [job?.status, jobId, refreshVillages]);

  // Selecting a village loads its summary, layers and boundary.
  useEffect(() => {
    if (!selected) return;
    setLoadError(null);
    Promise.all([api.summary(selected), api.layers(selected)])
      .then(([s, l]) => {
        setSummary(s);
        setLayers(l.layers);
        const ring = outerRing(s.village.boundary);
        if (ring) {
          setBoundary(s.village.boundary);
          const lons = ring.map((p) => p[0]);
          const lats = ring.map((p) => p[1]);
          setBounds([Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)]);
        }
      })
      .catch((e) => setLoadError((e as Error).message));
  }, [selected]);

  const toggle = (id: string) => setVisible((v) => ({ ...v, [id]: !(v[id] ?? true) }));

  return (
    <div className="app">
      <header>
        <h1>Village Pond Planner</h1>
        <span className="muted">terrain · catchment · runoff · storage — derived from your contour map</span>
      </header>
      <aside>
        <UploadPanel job={job} onSubmitted={(id) => { setBounds(null); setJobId(id); }} />
        <section className="panel">
          <h2>Village</h2>
          <select value={selected} onChange={(e) => { setBounds(null); setSelected(e.target.value); }} aria-label="Select village">
            <option value="">— select an analysed area —</option>
            {villages.map((v) => (
              <option key={v.id} value={v.id}>{v.name}</option>
            ))}
          </select>
          {loadError && <p className="error">{loadError}</p>}
          {!villages.length && <p className="muted">No analysed areas yet. Upload a contour map.</p>}
        </section>
        {summary && <SummaryCard summary={summary} />}
        {layers.length > 0 && <LayerControl layers={layers} visible={visible} onToggle={toggle} />}
      </aside>
      <MapView layers={layers} visible={visible} boundary={boundary} bounds={bounds} />
    </div>
  );
}
