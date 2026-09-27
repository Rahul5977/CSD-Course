import { useState } from "react";
import { api } from "../api";
import type { JobStatus } from "../types";
import { Badge, Callout, Panel, Progress } from "../ui";

export type Box = [number, number, number, number];

/** Must match POND_AREA_MIN_KM2 / POND_AREA_MAX_KM2 on the server, which is the real check. */
export const AREA_MIN_KM2 = 0.25;
export const AREA_MAX_KM2 = 25;

/** Box area in km² on a sphere: good to <1 % at village scale; the server re-measures in UTM. */
export function boxAreaKm2([w, s, e, n]: Box): number {
  const R = 6371.0088;
  const rad = Math.PI / 180;
  return R * R * Math.abs((e - w) * rad) * Math.abs(Math.sin(n * rad) - Math.sin(s * rad));
}

interface Props {
  job: JobStatus | null;
  selecting: boolean;
  selection: Box | null;
  onStartSelect: () => void;
  onCancel: () => void;
  onFlyTo: (lon: number, lat: number) => void;
  onSubmitted: (jobId: string) => void;
}

/** Phase 3 entry point: choose a land area on the map; elevation comes from Copernicus GLO-30. */
export function AreaPanel({ job, selecting, selection, onStartSelect, onCancel, onFlyTo, onSubmitted }: Props) {
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const area = selection ? boxAreaKm2(selection) : null;
  const inRange = area !== null && area >= AREA_MIN_KM2 && area <= AREA_MAX_KM2;
  const running = job && (job.status === "queued" || job.status === "running");

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`;
      const hits = (await (await fetch(url, { headers: { Accept: "application/json" } })).json()) as { lon: string; lat: string }[];
      if (!hits.length) setError(`No place called “${query}” found`);
      else onFlyTo(Number(hits[0].lon), Number(hits[0].lat));
    } catch {
      setError("Place search is unavailable — pan and zoom the map instead");
    } finally {
      setSearching(false);
    }
  };

  const analyse = async () => {
    if (!selection) return;
    setBusy(true);
    setError(null);
    try {
      onSubmitted((await api.analyzeArea(selection)).job_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const badge = selecting ? <Badge tone="info">drawing</Badge> : selection ? <Badge tone={inRange ? "ok" : "warn"}>{area!.toFixed(2)} km²</Badge> : undefined;

  return (
    <Panel title="Select land area" badge={badge} defaultOpen>
      <p className="muted">Find the village, then draw a box around the land. The pond site, its catchment and the water it can collect are computed for that box.</p>
      <form className="row" onSubmit={(e) => { e.preventDefault(); void search(); }}>
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Village or place…" aria-label="Search for a place" style={{ flex: 1, minWidth: 0 }} />
        <button type="submit" className="btn btn-sm btn-secondary" disabled={searching}>{searching ? "…" : "Go"}</button>
      </form>
      <div className="row">
        {selecting
          ? <button className="btn btn-sm btn-secondary" onClick={onCancel}>Cancel drawing</button>
          : <button className="btn btn-sm btn-secondary" onClick={onStartSelect} disabled={!!running}>{selection ? "Redraw area" : "Draw area on map"}</button>}
        <button className="btn btn-sm btn-primary" onClick={analyse} disabled={!inRange || busy || !!running || selecting}>{busy ? "Submitting…" : "Analyse area"}</button>
      </div>
      {selecting && <Callout>Click one corner of the land on the map, then the opposite corner.</Callout>}
      {selection && !inRange && !selecting && (
        <Callout tone="warn">Select between {AREA_MIN_KM2} and {AREA_MAX_KM2} km² — a village-sized area (this box is {area!.toFixed(2)} km²).</Callout>
      )}
      {error && <Callout tone="critical">{error}</Callout>}
      {job && (running || job.status === "failed") && <Progress status={job} />}
      {job?.error && <Callout tone="critical"><b>{job.error.code}</b> — {job.error.title}</Callout>}
    </Panel>
  );
}
