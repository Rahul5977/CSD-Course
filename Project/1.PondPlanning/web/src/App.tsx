import type { FeatureCollection, MultiPolygon, Polygon } from "geojson";
import { useCallback, useEffect, useState } from "react";
import { api, staleState } from "./api";
import { ResultsOverlay } from "./components/ResultsOverlay";
import { t, type Lang } from "./i18n";
import type { JobStatus } from "./types";
import { CatchmentPanel } from "./components/CatchmentPanel";
import { LayerControl } from "./components/LayerControl";
import { MapView } from "./components/MapView";
import { RainfallPanel, type RainfallStatistics } from "./components/RainfallPanel";
import { DesignPanel, type PondDesignResult } from "./components/WaterPanel";
import { LandPanel, type AvailableLand, type SuitabilityResult } from "./components/LandPanel";
import { SitesPanel } from "./components/SitesPanel";
import { SummaryCard } from "./components/SummaryCard";
import { UploadPanel } from "./components/UploadPanel";
import { useJob } from "./hooks/useJob";
import type { CatchmentResult, LayerDescriptor, PourPoint, SiteCandidate, SitingMethod, VillageOut, VillageSummary } from "./types";

type Bounds = [number, number, number, number];

/** Outer ring of a Polygon, or of the first part of a MultiPolygon (PostGIS stores the latter). */
function outerRing(geometry: Polygon | MultiPolygon | null): number[][] | null {
  if (!geometry) return null;
  return geometry.type === "Polygon" ? geometry.coordinates[0] : (geometry.coordinates[0]?.[0] ?? null);
}

const DEFAULT_VISIBLE: Record<string, boolean> = {
  satellite: true, hillshade: true, streams: true, contours: true, catchment: true, sites: true, boundary: true, pond: true,
};

export default function App() {
  const [villages, setVillages] = useState<VillageOut[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [summary, setSummary] = useState<VillageSummary | null>(null);
  const [layers, setLayers] = useState<LayerDescriptor[]>([]);
  const [boundary, setBoundary] = useState<Polygon | MultiPolygon | null>(null);
  const [bounds, setBounds] = useState<Bounds | null>(null);
  const [visible, setVisible] = useState<Record<string, boolean>>(DEFAULT_VISIBLE);
  const [contourInterval, setContourInterval] = useState(2);
  const [contours, setContours] = useState<FeatureCollection | null>(null);
  const [streams, setStreams] = useState<FeatureCollection | null>(null);
  const [catchment, setCatchment] = useState<CatchmentResult | null>(null);
  const [catchmentBusy, setCatchmentBusy] = useState(false);
  const [catchmentError, setCatchmentError] = useState<string | null>(null);
  const [sites, setSites] = useState<SiteCandidate[]>([]);
  const [siting, setSiting] = useState<SitingMethod | null>(null);
  const [rationale, setRationale] = useState<string | null>(null);
  const [land, setLand] = useState<AvailableLand | null>(null);
  const [suitability, setSuitability] = useState<SuitabilityResult | null>(null);
  const [landBusy, setLandBusy] = useState(false);
  const [landError, setLandError] = useState<string | null>(null);
  const [design, setDesign] = useState<PondDesignResult | null>(null);
  const [designBusy, setDesignBusy] = useState(false);
  const [designError, setDesignError] = useState<string | null>(null);
  const [rain, setRain] = useState<RainfallStatistics | null>(null);
  const [rainBusy, setRainBusy] = useState(false);
  const [rainError, setRainError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [progress, setProgress] = useState<Record<string, JobStatus | null>>({});
  const [lang, setLang] = useState<Lang>(() => { try { return (localStorage.getItem("lang") as Lang) || "en"; } catch { return "en"; } });
  const [stale, setStale] = useState(staleState.stale);
  const job = useJob(jobId);

  useEffect(() => {
    staleState.listeners.add(setStale);
    return () => { staleState.listeners.delete(setStale); };
  }, []);
  useEffect(() => { try { localStorage.setItem("lang", lang); } catch { /* private mode */ } }, [lang]);
  const track = (key: string) => (status: JobStatus) => setProgress((p) => ({ ...p, [key]: status.status === "running" || status.status === "queued" ? status : null }));

  const refreshVillages = useCallback(async () => {
    const page = await api.villages();
    setVillages(page.items);
    return page.items;
  }, []);

  useEffect(() => {
    refreshVillages().catch((e) => setLoadError((e as Error).message));
  }, [refreshVillages]);

  // When the upload job finishes: select its village and show its sites + catchment.
  useEffect(() => {
    if (job?.status !== "succeeded" || !jobId) return;
    api.contourResult(jobId).then(async (result) => {
      await refreshVillages();
      setSelected(result.village_id);
      setSites(result.candidate_sites);
      setSiting(result.siting);
      setRationale(result.location_rationale);
      setCatchment(result.catchment);
    });
  }, [job?.status, jobId, refreshVillages]);

  // Selecting a village loads its summary, layers, boundary, streams and sites.
  useEffect(() => {
    if (!selected) return;
    setLoadError(null);
    Promise.all([api.summary(selected), api.layers(selected), api.streams(selected).catch(() => null), api.siting(selected).catch(() => null)])
      .then(([s, l, st, si]) => {
        setSummary(s);
        setLayers(l.layers);
        setStreams(st?.geojson ?? null);
        api.availableLand(selected).then(setLand).catch(() => setLand(null));
        setSuitability(null);
        if (si) {
          setSites(si.candidate_sites);
          setSiting(si.siting);
        }
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

  // Rainfall statistics at the village centroid (FR5), once the summary is known.
  useEffect(() => {
    if (!summary) return;
    const [lon, lat] = summary.village.centroid;
    setRainBusy(true);
    setRainError(null);
    api.rainfallStatistics(lon, lat)
      .then(setRain)
      .catch((e) => setRainError((e as Error).message))
      .finally(() => setRainBusy(false));
  }, [summary]);

  useEffect(() => {
    if (!selected) return;
    api.contours(selected, contourInterval).then((c) => setContours(c.geojson)).catch(() => setContours(null));
  }, [selected, contourInterval]);

  const delineate = useCallback(
    async (point: PourPoint) => {
      if (!selected) return;
      setCatchmentBusy(true);
      setCatchmentError(null);
      try {
        setCatchment(await api.catchment(selected, point, track("catchment")));
      } catch (e) {
        setCatchmentError((e as Error).message);
      } finally {
        setCatchmentBusy(false);
      }
    },
    [selected],
  );

  const assessLand = useCallback(async () => {
    if (!selected) return;
    setLandBusy(true);
    setLandError(null);
    try {
      const result = await api.suitability(selected, 8, track("land"));
      setSuitability(result);
      setLand(await api.availableLand(selected));
      setLayers((await api.layers(selected)).layers);
      setVisible((v) => ({ ...v, available_land: true, suitability: true }));
    } catch (e) {
      setLandError((e as Error).message);
    } finally {
      setLandBusy(false);
    }
  }, [selected]);

  const designPond = useCallback(async () => {
    if (!selected || !catchment) return;
    setDesignBusy(true);
    setDesignError(null);
    try {
      setDesign(await api.pondDesign(selected, catchment.snapped_point, 0.75, track("design")));
    } catch (e) {
      setDesignError((e as Error).message);
    } finally {
      setDesignBusy(false);
    }
  }, [selected, catchment]);

  const toggle = (id: string) => setVisible((v) => ({ ...v, [id]: !(v[id] ?? false) }));

  return (
    <div className="app">
      <header>
        <h1>{t("title", lang)}</h1>
        <span className="muted">{t("tagline", lang)}</span>
        {stale && <span className="badge-offline" role="status">{t("offline", lang)}</span>}
        <button className="lang" onClick={() => setLang(lang === "en" ? "hi" : "en")} aria-label="Toggle language">{lang === "en" ? "हिन्दी" : "EN"}</button>
      </header>
      <aside>
        <UploadPanel job={job} onSubmitted={(id) => { setBounds(null); setCatchment(null); setSites([]); setJobId(id); }} />
        <section className="panel">
          <h2>Village</h2>
          <select value={selected} onChange={(e) => { setBounds(null); setCatchment(null); setSites([]); setSiting(null); setRationale(null); setSelected(e.target.value); }} aria-label="Select village">
            <option value="">— select an analysed area —</option>
            {villages.map((v) => (
              <option key={v.id} value={v.id}>{v.name}</option>
            ))}
          </select>
          {loadError && <p className="error">{loadError}</p>}
          {!villages.length && <p className="muted">No analysed areas yet. Upload a contour map.</p>}
        </section>
        {summary && <SummaryCard summary={summary} />}
        {selected && <CatchmentPanel catchment={catchment} busy={catchmentBusy} error={catchmentError} progress={progress.catchment ?? null} />}
        {selected && <RainfallPanel stats={rain} busy={rainBusy} error={rainError} />}
        {selected && <LandPanel land={land} suitability={suitability} busy={landBusy} error={landError} onAssess={assessLand} onPick={(s) => delineate(s.location)} canAssess={!!selected} progress={progress.land ?? null} />}
        {selected && <DesignPanel design={design} busy={designBusy} error={designError} onDesign={designPond} canDesign={!!catchment} progress={progress.design ?? null} />}
        <SitesPanel sites={sites} method={siting} rationale={rationale} onPick={(s) => delineate(s.location)} />
        {layers.length > 0 && <LayerControl layers={layers} visible={visible} onToggle={toggle} contourInterval={contourInterval} onInterval={setContourInterval} />}
      </aside>
      <main className="mapwrap">
        <MapView layers={layers} visible={visible} boundary={boundary} bounds={bounds} contours={contours} streams={streams} catchment={catchment} sites={sites} land={land?.geojson ?? null} pond={design && catchment ? { lon: catchment.snapped_point.lon, lat: catchment.snapped_point.lat, lengthM: design.dimensions.top_length.value, widthM: design.dimensions.top_width.value } : null} onClick={delineate} />
        <ResultsOverlay site={catchment?.snapped_point ?? null} catchment={catchment} rain={rain} design={design} villageName={summary?.village.name ?? null} />
      </main>
    </div>
  );
}
