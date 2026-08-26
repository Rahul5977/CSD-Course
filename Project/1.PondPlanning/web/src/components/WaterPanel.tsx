import type { JobStatus, PondDesignResult, RunoffResult } from "../types";
import { Badge, Empty, ErrorBox, Facts, Panel, Progress, Q, Qty, Warnings } from "../ui";

const LABEL: Record<string, string> = { scs_cn: "SCS-CN (daily)", rational: "Runoff coefficient", empirical_strange: "Strange's table" };

/** FR6: three methods as a range, the recommended one first. */
export function RunoffPanel({ runoff }: { runoff: RunoffResult }) {
  return (
    <>
      <table className="table">
        <thead>
          <tr><th>Method</th><th>Annual runoff</th><th>C</th></tr>
        </thead>
        <tbody>
          {runoff.results.map((r) => (
            <tr key={r.method} style={r.method === runoff.recommended.method ? { fontWeight: 600 } : undefined}>
              <td title={r.reference}>{LABEL[r.method] ?? r.method}</td>
              <td><Q q={r.annual_runoff_volume} /></td>
              <td>{r.runoff_coefficient.value.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">Methods disagree by {runoff.spread_pct.display}; SCS-CN on the daily series is the design figure.</p>
      <Warnings items={runoff.warnings} />
    </>
  );
}

/** FR7: dimensions, storage, EAV curve, reliability, BoQ, confidence. */
export function DesignPanel({ design, busy, error, onDesign, canDesign, progress }: { design: PondDesignResult | null; busy: boolean; error: string | null; onDesign: () => void; canDesign: boolean; progress: JobStatus | null }) {
  const W = 320, H = 120, pad = 24;
  const curve = design?.eav_curve ?? [];
  const maxV = Math.max(...curve.map((p) => p.cumulative_volume.value), 1);
  const maxH = Math.max(...curve.map((p) => p.elevation.value), 1);
  const badge = busy ? <Badge tone="info">running</Badge> : error ? <Badge tone="error">failed</Badge>
    : design ? <Badge tone={design.confidence === "high" ? "ok" : design.confidence === "moderate" ? "info" : "warn"}>confidence {design.confidence}</Badge> : undefined;
  return (
    <Panel title="Pond design" badge={badge} footer={<><button className="btn btn-sm btn-primary" onClick={onDesign} disabled={!canDesign || busy}>{busy ? "Designing…" : design ? "Redesign at the outlet" : "Design a pond at the outlet"}</button><span className="muted">heavy queue · ~15 s</span></>}>
      {!canDesign && !design && <Empty>Delineate a catchment first — click the map or pick a suggested site.</Empty>}
      {busy && <Progress status={progress} label="queued" />}
      {error && !busy && <ErrorBox message={error} />}
      {design && !busy && (
        <>
          <div className="qty-grid">
            <Qty q={design.gross_storage} label="Gross storage" />
            <Qty q={design.reliability} label="Fills to 90 %" note="of years" />
            <Qty q={design.dimensions.depth} label="Depth" note="chosen by cost" />
            <Qty q={design.bill_of_quantities.indicative_cost} label="Indicative cost" />
          </div>
          <p className="small" title={design.confidence_rationale}><span className="muted">Why this confidence:</span> {design.confidence_rationale}</p>
          <Facts rows={[
            ["Top", <>{design.dimensions.top_length.value.toFixed(0)} × {design.dimensions.top_width.value.toFixed(0)} m</>],
            ["Bottom", <>{design.dimensions.bottom_length.value.toFixed(0)} × {design.dimensions.bottom_width.value.toFixed(0)} m</>],
            ["Side slope", <>{design.dimensions.side_slope.value}:1 · freeboard <Q q={design.dimensions.freeboard} /></>],
            ["Live / dead", <><Q q={design.live_storage} /> / <Q q={design.dead_storage} /></>],
            ["Excavation", <Q q={design.bill_of_quantities.excavation_volume} />],
            ["Embankment", <Q q={design.bill_of_quantities.embankment_volume} />],
          ]} />
          <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Elevation-area-volume curve">
            <polyline fill="none" stroke="#0b6e8f" strokeWidth="2" points={curve.map((p) => `${pad + ((W - 2 * pad) * p.cumulative_volume.value) / maxV},${H - pad - ((H - 2 * pad) * p.elevation.value) / maxH}`).join(" ")} />
            <text x={pad} y={12} fontSize="9" fill="#5b6770">depth (m) vs stored volume (m³) — EAV curve of the site</text>
            <text x={W - pad} y={H - 6} fontSize="9" textAnchor="end" fill="#5b6770">{Math.round(maxV).toLocaleString("en-IN")} m³</text>
            <text x={4} y={pad + 4} fontSize="9" fill="#5b6770">{maxH} m</text>
          </svg>
          <h3 className="small" style={{ marginTop: 4 }}>Runoff — three methods (FR6)</h3>
          <RunoffPanel runoff={design.runoff} />
          <p className="muted">{design.bill_of_quantities.cost_basis}</p>
          <Warnings items={design.warnings} />
        </>
      )}
    </Panel>
  );
}
