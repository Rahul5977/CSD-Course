import type { CatchmentResult, PondDesignResult, RainfallStatistics } from "../types";
import { Badge, Qty } from "../ui";

/** FR8: the six PDF-listed results, together, as one card over the map. */
export function ResultsOverlay({ site, catchment, rain, design, villageName }: {
  site: { lon: number; lat: number } | null;
  catchment: CatchmentResult | null;
  rain: RainfallStatistics | null;
  design: PondDesignResult | null;
  villageName: string | null;
}) {
  if (!villageName) return null;
  const years = design ? Math.round(design.reliability.value * 25) : null;
  return (
    <aside className="overlay" aria-label="Results overlay">
      <h3>Results · {villageName}</h3>
      <p className="small">{site ? `Pond location ${site.lat.toFixed(5)} N, ${site.lon.toFixed(5)} E` : <span className="muted">Click the map for a pond location</span>}</p>
      <div className="qty-grid">
        <Qty q={catchment?.area} label="Catchment" />
        <Qty q={rain?.dependable_75} label="Rainfall (75 %)" />
        <Qty q={design?.runoff.recommended.annual_runoff_volume} label="Runoff (SCS-CN)" />
        <Qty q={design?.gross_storage} label="Gross storage" />
      </div>
      {design && (
        <p className="small">Pond <b>{design.dimensions.top_length.value.toFixed(0)} × {design.dimensions.top_width.value.toFixed(0)} m</b>, {design.dimensions.depth.display} · fills in about {years} of every 25 years</p>
      )}
      {design && <div className="row"><Badge tone={design.confidence === "high" ? "ok" : design.confidence === "moderate" ? "info" : "warn"}>confidence {design.confidence}</Badge></div>}
    </aside>
  );
}
