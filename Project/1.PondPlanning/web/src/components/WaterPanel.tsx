import type { JobStatus, QuantityOut, ResultWarning } from "../types";
import { Progress } from "./CatchmentPanel";

function Q({ q }: { q: QuantityOut }) {
  return <strong title={q.method ?? undefined}>{q.display ?? `${q.value} ${q.unit}`}</strong>;
}

export interface RunoffMethodResult {
  method: string;
  annual_runoff_volume: QuantityOut;
  runoff_coefficient: QuantityOut;
  parameters: Record<string, QuantityOut>;
  reference: string;
}
export interface RunoffResult {
  catchment_area: QuantityOut;
  results: RunoffMethodResult[];
  recommended: RunoffMethodResult;
  spread_pct: QuantityOut;
  warnings: ResultWarning[];
}
export interface PondDesignResult {
  dimensions: Record<string, QuantityOut>;
  gross_storage: QuantityOut;
  live_storage: QuantityOut;
  dead_storage: QuantityOut;
  eav_curve: { elevation: QuantityOut; surface_area: QuantityOut; cumulative_volume: QuantityOut }[];
  reliability: QuantityOut;
  bill_of_quantities: { excavation_volume: QuantityOut; embankment_volume: QuantityOut; indicative_cost: QuantityOut; cost_basis: string };
  confidence: "low" | "moderate" | "high";
  confidence_rationale: string;
  rainfall_summary: Record<string, QuantityOut>;
  runoff: RunoffResult;
  warnings: ResultWarning[];
}

const LABEL: Record<string, string> = { scs_cn: "SCS-CN (daily)", rational: "Runoff coefficient", empirical_strange: "Strange's table" };

/** FR6: three methods as a range, the recommended one first. */
export function RunoffPanel({ runoff }: { runoff: RunoffResult }) {
  return (
    <>
      <table className="methods">
        <thead>
          <tr><th>Method</th><th>Annual runoff</th><th>C</th></tr>
        </thead>
        <tbody>
          {runoff.results.map((r) => (
            <tr key={r.method} className={r.method === runoff.recommended.method ? "recommended" : ""}>
              <td title={r.reference}>{LABEL[r.method] ?? r.method}</td>
              <td><Q q={r.annual_runoff_volume} /></td>
              <td>{r.runoff_coefficient.value.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">Methods disagree by {runoff.spread_pct.display}; SCS-CN on the daily series is the design figure.</p>
      {runoff.warnings.map((w) => (
        <p key={w.code} className={`warn warn-${w.severity}`}>{w.message}</p>
      ))}
    </>
  );
}

/** FR7: dimensions, storage, EAV curve, reliability, BoQ, confidence. */
export function DesignPanel({ design, busy, error, onDesign, canDesign, progress }: { design: PondDesignResult | null; busy: boolean; error: string | null; onDesign: () => void; canDesign: boolean; progress: JobStatus | null }) {
  const W = 300, H = 120, pad = 24;
  const curve = design?.eav_curve ?? [];
  const maxV = Math.max(...curve.map((p) => p.cumulative_volume.value), 1);
  const maxH = Math.max(...curve.map((p) => p.elevation.value), 1);
  return (
    <section className="panel">
      <h2>Pond design</h2>
      <div className="row">
        <button onClick={onDesign} disabled={!canDesign || busy}>{busy ? "Designing…" : "Design a pond at the outlet"}</button>
      </div>
      {!canDesign && <p className="muted">Delineate a catchment first (click the map or pick a site).</p>}
      {busy && <Progress status={progress} />}
      {error && <p className="error">{error}</p>}
      {design && (
        <>
          <p className="verdict">
            Fills in <Q q={design.reliability} /> of years · gross <Q q={design.gross_storage} />
            <span className={`conf conf-${design.confidence}`} title={design.confidence_rationale}> {design.confidence} confidence</span>
          </p>
          <dl>
            <dt>Depth</dt><dd><Q q={design.dimensions.depth} /></dd>
            <dt>Top</dt><dd><Q q={design.dimensions.top_length} /> × <Q q={design.dimensions.top_width} /></dd>
            <dt>Bottom</dt><dd><Q q={design.dimensions.bottom_length} /> × <Q q={design.dimensions.bottom_width} /></dd>
            <dt>Side slope</dt><dd>{design.dimensions.side_slope.value}:1 · freeboard <Q q={design.dimensions.freeboard} /></dd>
            <dt>Live / dead</dt><dd><Q q={design.live_storage} /> / <Q q={design.dead_storage} /></dd>
            <dt>Excavation</dt><dd><Q q={design.bill_of_quantities.excavation_volume} /></dd>
            <dt>Embankment</dt><dd><Q q={design.bill_of_quantities.embankment_volume} /></dd>
            <dt>Indicative cost</dt><dd><Q q={design.bill_of_quantities.indicative_cost} /></dd>
          </dl>
          <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Elevation-area-volume curve">
            <polyline fill="none" stroke="#0b6e8f" strokeWidth="2" points={curve.map((p) => `${pad + ((W - 2 * pad) * p.cumulative_volume.value) / maxV},${H - pad - ((H - 2 * pad) * p.elevation.value) / maxH}`).join(" ")} />
            <text x={pad} y={12} fontSize="9" fill="#5b6770">depth (m) vs stored volume (m³) — EAV curve</text>
            <text x={W - pad} y={H - 6} fontSize="9" textAnchor="end" fill="#5b6770">{Math.round(maxV).toLocaleString()} m³</text>
            <text x={4} y={pad + 4} fontSize="9" fill="#5b6770">{maxH} m</text>
          </svg>
          <h3 className="sub">Runoff (FR6)</h3>
          <RunoffPanel runoff={design.runoff} />
          <p className="muted">{design.bill_of_quantities.cost_basis}</p>
          {design.warnings.map((w) => (
            <p key={w.code} className={`warn warn-${w.severity}`}>{w.message}</p>
          ))}
        </>
      )}
    </section>
  );
}
