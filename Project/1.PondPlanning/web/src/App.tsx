import type { FeatureCollection, MultiPolygon, Polygon } from "geojson";
import { useCallback, useEffect, useState } from "react";
import { api, staleState } from "./api";
import { CatchmentPanel } from "./components/CatchmentPanel";
import { LandPanel } from "./components/LandPanel";
import { LayerControl } from "./components/LayerControl";
import { MapView } from "./components/MapView";
import { RainfallPanel } from "./components/RainfallPanel";
import { RecommendationPanel } from "./components/RecommendationPanel";
import { ResultsOverlay } from "./components/ResultsOverlay";
import { SitesPanel } from "./components/SitesPanel";
import { SummaryCard } from "./components/SummaryCard";
import { UploadPanel } from "./components/UploadPanel";
import { DesignPanel } from "./components/WaterPanel";
import { useJob } from "./hooks/useJob";
import { useTask } from "./hooks/useTask";
import { t, type Lang } from "./i18n";
import type {
  AvailableLand,
  CatchmentResult,
  LayerDescriptor,
  PondDesignResult,
  PourPoint,
  RainfallStatistics,
  Session,
  SiteCandidate,
  SitingMethod,
  SuitabilityResult,
  VillageOut,
  VillageSummary,
} from "./types";
import { Badge, Mark } from "./ui";

type Bounds = [number, number, number, number];

/** Outer ring of a Polygon, or of the first part of a MultiPolygon (PostGIS stores the latter). */
function outerRing(geometry: Polygon | MultiPolygon | null): number[][] | null {
  if (!geometry) return null;
  return geometry.type === "Polygon" ? geometry.coordinates[0] : (geometry.coordinates[0]?.[0] ?? null);
}

/** Bounding box of a boundary ring, or null when there is no ring. */
function boundsOf(geometry: Polygon | MultiPolygon | null): Bounds | null {
  const ring = outerRing(geometry);
  if (!ring) return null;
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
}

const DEFAULT_VISIBLE: Record<string, boolean> = {
  satellite: true, hillshade: true, streams: true, contours: true, catchment: true, sites: true, boundary: true, pond: true,
};

/** The workspace at /app: one selected village, its terrain, and the four analyses on it. */
export default function App() {
  // --- the village and its terrain ---
  const [villages, setVillages] = useState<VillageOut[]>([]);
  const [selected, setSelected] = useState<string>(() => new URLSearchParams(window.location.search).get("village") ?? "");
  const [summary, setSummary] = useState<VillageSummary | null>(null);
  const [layers, setLayers] = useState<LayerDescriptor[]>([]);
  const [boundary, setBoundary] = useState<Polygon | MultiPolygon | null>(null);
  const [bounds, setBounds] = useState<Bounds | null>(null);
  const [visible, setVisible] = useState<Record<string, boolean>>(DEFAULT_VISIBLE);
  const [contourInterval, setContourInterval] = useState(2);
  const [contours, setContours] = useState<FeatureCollection | null>(null);
  const [streams, setStreams] = useState<FeatureCollection | null>(null);
  const [sites, setSites] = useState<SiteCandidate[]>([]);
  const [siting, setSiting] = useState<SitingMethod | null>(null);
  const [rationale, setRationale] = useState<string | null>(null);
  const [land, setLand] = useState<AvailableLand | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // --- the analyses: each one result · busy · error · progress ---
  const catchment = useTask<CatchmentResult>();
  const rain = useTask<RainfallStatistics>();
  const design = useTask<PondDesignResult>();
  const suitability = useTask<SuitabilityResult>();

  // --- session and shell state ---
  const [session, setSession] = useState<Session | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [lang, setLang] = useState<Lang>(() => { try { return (localStorage.getItem("lang") as Lang) || "en"; } catch { return "en"; } });
  const [stale, setStale] = useState(staleState.stale);
  const job = useJob(jobId);

  useEffect(() => {
    staleState.listeners.add(setStale);
    return () => { staleState.listeners.delete(setStale); };
  }, []);
  useEffect(() => { try { localStorage.setItem("lang", lang); } catch { /* private mode */ } }, [lang]);

  const refreshVillages = useCallback(async () => {
    const page = await api.villages();
    setVillages(page.items);
    return page.items;
  }, []);

  useEffect(() => {
    refreshVillages().catch((e) => setLoadError((e as Error).message));
  }, [refreshVillages]);

  const { set: setCatchment, reset: resetCatchment } = catchment;
  const { reset: resetDesign } = design;
  const { reset: resetSuitability } = suitability;

  /** Switch village: clear everything derived from the previous one. */
  const selectVillage = useCallback((id: string) => {
    setBounds(null);
    setSites([]);
    setSiting(null);
    setRationale(null);
    resetCatchment();
    resetDesign();
    resetSuitability();
    setSelected(id);
  }, [resetCatchment, resetDesign, resetSuitability]);

  // When the upload job finishes: select its village and show its sites + catchment.
  useEffect(() => {
    if (job?.status !== "succeeded" || !jobId) return;
    api.contourResult(jobId).then(async (result) => {
      await refreshVillages();
      selectVillage(result.village_id);
      setSites(result.candidate_sites);
      setSiting(result.siting);
      setRationale(result.location_rationale);
      if (result.catchment) setCatchment(result.catchment);
    });
  }, [job?.status, jobId, refreshVillages, selectVillage, setCatchment]);

  // Selecting a village loads its summary, layers, boundary, streams, sites and land.
  useEffect(() => {
    if (!selected) return;
    setLoadError(null);
    Promise.all([api.summary(selected), api.layers(selected), api.streams(selected).catch(() => null), api.siting(selected).catch(() => null)])
      .then(([s, l, st, si]) => {
        setSummary(s);
        setLayers(l.layers);
        setStreams(st?.geojson ?? null);
        api.availableLand(selected).then(setLand).catch(() => setLand(null));
        if (si) {
          setSites(si.candidate_sites);
          setSiting(si.siting);
        }
        setBoundary(s.village.boundary);
        setBounds(boundsOf(s.village.boundary));
      })
      .catch((e) => setLoadError((e as Error).message));
  }, [selected]);

  // Rainfall statistics at the village centroid (FR5), once the summary is known.
  const runRain = rain.run;
  useEffect(() => {
    if (!summary) return;
    const [lon, lat] = summary.village.centroid;
    void runRain(() => api.rainfallStatistics(lon, lat));
  }, [summary, runRain]);

  useEffect(() => {
    if (!selected) return;
    api.contours(selected, contourInterval).then((c) => setContours(c.geojson)).catch(() => setContours(null));
  }, [selected, contourInterval]);

  const runCatchment = catchment.run;
  const delineate = useCallback((point: PourPoint) => {
    if (!selected) return;
    void runCatchment((onProgress) => api.catchment(selected, point, onProgress));
  }, [selected, runCatchment]);

  const runSuitability = suitability.run;
  const assessLand = useCallback(() => {
    if (!selected) return;
    void runSuitability(async (onProgress) => {
      const result = await api.suitability(selected, 8, onProgress);
      setLand(await api.availableLand(selected));
      setLayers((await api.layers(selected)).layers);
      setVisible((v) => ({ ...v, available_land: true, suitability: true }));
      return result;
    });
  }, [selected, runSuitability]);

  const runDesign = design.run;
  const outlet = catchment.value?.snapped_point ?? null;
  const designPond = useCallback(() => {
    if (!selected || !outlet) return;
    void runDesign((onProgress) => api.pondDesign(selected, outlet, 0.75, onProgress));
  }, [selected, outlet, runDesign]);

  const toggle = (id: string) => setVisible((v) => ({ ...v, [id]: !(v[id] ?? false) }));
  const pond = design.value && outlet
    ? { lon: outlet.lon, lat: outlet.lat, lengthM: design.value.dimensions.top_length.value, widthM: design.value.dimensions.top_width.value }
    : null;

  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="/" title="Back to the landing page"><Mark light /><span className="brand-text">{t("title", lang)}</span></a>
        <select value={selected} onChange={(e) => selectVillage(e.target.value)} aria-label="Select village">
          <option value="">— select an analysed area —</option>
          {villages.map((v) => (
            <option key={v.id} value={v.id}>{v.name}{v.district ? ` · ${v.district}` : ""}</option>
          ))}
        </select>
        {stale && <Badge tone="offline">{t("offline", lang)}</Badge>}
        {rain.value?.fallback_used === "cache" && !stale && <Badge tone="stale">rainfall from cache</Badge>}
        <span className="spacer" />
        {session && <span className="small" style={{ color: "#cfd8dc" }}>{session.username} · {session.role}</span>}
        <button className="btn btn-sm lang" onClick={() => setLang(lang === "en" ? "hi" : "en")} aria-label="Toggle language" lang={lang === "en" ? "hi" : "en"}>{lang === "en" ? "हिन्दी" : "EN"}</button>
      </header>
      <aside className="rail" aria-label="Analysis panels">
        <UploadPanel job={job} hasVillages={villages.length > 0} onSubmitted={(id) => { setBounds(null); resetCatchment(); setSites([]); setJobId(id); }} />
        {loadError && <div className="callout callout-critical"><b>Could not load</b> — {loadError}</div>}
        {!villages.length && !job && <div className="empty"><span>No analysed areas yet. Upload a contour map to begin.</span></div>}
        {summary && <SummaryCard summary={summary} />}
        <SitesPanel sites={sites} method={siting} rationale={rationale} onPick={(s) => delineate(s.location)} />
        {selected && <CatchmentPanel catchment={catchment.value} busy={catchment.busy} error={catchment.error} progress={catchment.progress} onDesign={designPond} designBusy={design.busy} />}
        {selected && <RainfallPanel stats={rain.value} busy={rain.busy} error={rain.error} />}
        {selected && <DesignPanel design={design.value} busy={design.busy} error={design.error} onDesign={designPond} canDesign={!!outlet} progress={design.progress} />}
        {selected && <LandPanel land={land} suitability={suitability.value} busy={suitability.busy} error={suitability.error} onAssess={assessLand} onPick={(s) => delineate(s.location)} canAssess={!!selected} progress={suitability.progress} />}
        {design.value && <RecommendationPanel designJobId={design.value.job_id ?? null} session={session} onLogin={setSession} onLogout={() => setSession(null)} />}
        {layers.length > 0 && <LayerControl layers={layers} visible={visible} onToggle={toggle} contourInterval={contourInterval} onInterval={setContourInterval} />}
      </aside>
      <main className="mapwrap">
        <MapView layers={layers} visible={visible} boundary={boundary} bounds={bounds} contours={contours} streams={streams} catchment={catchment.value} sites={sites} land={land?.geojson ?? null} pond={pond} onClick={delineate} />
        {selected && !catchment.value && !catchment.busy && <span className="hint" role="status">Click anywhere on the map for the catchment of that point</span>}
        <ResultsOverlay site={outlet} catchment={catchment.value} rain={rain.value} design={design.value} villageName={summary?.village.name ?? null} />
      </main>
    </div>
  );
}
