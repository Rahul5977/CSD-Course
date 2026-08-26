import type { QuantityOut, ResultWarning } from "../types";

export interface LandParcel {
  parcel_id: string;
  ownership_class: string;
  area: QuantityOut;
  mean_slope: QuantityOut;
  lulc_class: string;
  eligible: boolean;
}
export interface AvailableLand {
  constraints_applied: string[];
  total_eligible_area: QuantityOut;
  parcels: LandParcel[];
  geojson: GeoJSON.FeatureCollection;
  warnings: ResultWarning[];
}
export interface CriterionScore {
  criterion: string;
  raw_value: QuantityOut;
  normalised_score: QuantityOut;
  weight: QuantityOut;
  contribution: QuantityOut;
}
export interface SuitableSite {
  rank: number;
  location: { lon: number; lat: number };
  total_score: QuantityOut;
  criteria: CriterionScore[];
  catchment_area: QuantityOut;
  estimated_storage: QuantityOut;
}
export interface SuitabilityResult {
  sites: SuitableSite[];
  weights: Record<string, number>;
  consistency_ratio: number;
  consistency_acceptable: boolean;
  warnings: ResultWarning[];
}

/** FR3: available land (constraints + parcels) and the AHP-ranked sites with a per-criterion breakdown. */
export function LandPanel({ land, suitability, busy, error, onAssess, onPick, canAssess }: {
  land: AvailableLand | null;
  suitability: SuitabilityResult | null;
  busy: boolean;
  error: string | null;
  onAssess: () => void;
  onPick: (site: SuitableSite) => void;
  canAssess: boolean;
}) {
  return (
    <section className="panel">
      <h2>Available land &amp; suitability</h2>
      <div className="row">
        <button onClick={onAssess} disabled={!canAssess || busy}>{busy ? "Assessing…" : "Assess land & rank sites"}</button>
      </div>
      {error && <p className="error">{error}</p>}
      {land && (
        <>
          <p className="verdict">Eligible for excavation: <strong>{land.total_eligible_area.display}</strong> in {land.parcels.length} patches.</p>
          <details>
            <summary className="muted">Constraints applied ({land.constraints_applied.length})</summary>
            <ul className="muted small">{land.constraints_applied.map((c) => <li key={c}>{c}</li>)}</ul>
          </details>
          <ul className="parcels">
            {land.parcels.slice(0, 6).map((p) => (
              <li key={p.parcel_id}><strong>{p.area.display}</strong> · {p.lulc_class} · slope {p.mean_slope.value.toFixed(1)} % · ownership {p.ownership_class}</li>
            ))}
          </ul>
        </>
      )}
      {suitability && (
        <>
          <h3 className="sub">AHP ranking · CR {suitability.consistency_ratio.toFixed(3)} {suitability.consistency_acceptable ? "✓ < 0.10" : "✗ ≥ 0.10"}</h3>
          <p className="muted">weights {Object.entries(suitability.weights).map(([k, v]) => `${k} ${v.toFixed(2)}`).join(" · ")}</p>
          <ol className="sites">
            {suitability.sites.map((s) => (
              <li key={s.rank}>
                <button className="linkish" onClick={() => onPick(s)} title="Delineate this site's catchment">#{s.rank} · score {s.total_score.value.toFixed(2)}</button>
                <small className="muted">{s.catchment_area.display} upstream · {s.estimated_storage.display}</small>
                <div className="bars">
                  {s.criteria.map((c) => (
                    <span key={c.criterion} className="bar-mini" title={`${c.criterion}: raw ${c.raw_value.display}, score ${c.normalised_score.value.toFixed(2)} × weight ${c.weight.value.toFixed(2)} = ${c.contribution.value.toFixed(3)}`}>
                      <i style={{ width: `${c.normalised_score.value * 100}%` }} />{c.criterion}
                    </span>
                  ))}
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
      {(land?.warnings ?? []).concat(suitability?.warnings ?? []).filter((w) => w.code !== "ahp_matrix").map((w) => (
        <p key={w.code + w.message.slice(0, 12)} className={`warn warn-${w.severity}`}>{w.message}</p>
      ))}
    </section>
  );
}
