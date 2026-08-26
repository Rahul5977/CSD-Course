import type { CatchmentResult, QuantityOut } from "../types";
import type { PondDesignResult } from "./WaterPanel";
import type { RainfallStatistics } from "./RainfallPanel";

function Q({ q }: { q: QuantityOut | undefined }) {
  return q ? <strong title={q.method ?? undefined}>{q.display ?? `${q.value} ${q.unit}`}</strong> : <span className="muted">—</span>;
}

/** FR8: the six PDF-listed results, together, as one stats panel over the map. */
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
      <h3>{villageName}</h3>
      <dl>
        <dt>Pond location</dt>
        <dd>{site ? `${site.lat.toFixed(5)} N, ${site.lon.toFixed(5)} E` : <span className="muted">click the map</span>}</dd>
        <dt>Catchment area</dt>
        <dd><Q q={catchment?.area} /></dd>
        <dt>Annual rainfall (75 %)</dt>
        <dd><Q q={rain?.dependable_75} /></dd>
        <dt>Runoff volume (SCS-CN)</dt>
        <dd><Q q={design?.runoff.recommended.annual_runoff_volume} /></dd>
        <dt>Pond dimensions</dt>
        <dd>{design ? `${design.dimensions.top_length.value.toFixed(0)} × ${design.dimensions.top_width.value.toFixed(0)} m, ${design.dimensions.depth.display}` : <span className="muted">—</span>}</dd>
        <dt>Storage</dt>
        <dd><Q q={design?.gross_storage} /></dd>
      </dl>
      {design && years !== null && <p className="verdict">Fills in about {years} of every 25 years.</p>}
    </aside>
  );
}
