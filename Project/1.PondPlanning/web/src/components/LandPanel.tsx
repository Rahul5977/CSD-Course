import type { AvailableLand, JobStatus, SuitabilityResult, SuitableSite } from "../types";
import { Badge, Empty, ErrorBox, Panel, Progress, Warnings } from "../ui";

/** FR3: available land (constraints + parcels) and the AHP-ranked sites with a per-criterion breakdown. */
export function LandPanel({ land, suitability, busy, error, onAssess, onPick, canAssess, progress }: {
  land: AvailableLand | null;
  suitability: SuitabilityResult | null;
  busy: boolean;
  error: string | null;
  onAssess: () => void;
  onPick: (site: SuitableSite) => void;
  canAssess: boolean;
  progress: JobStatus | null;
}) {
  const badge = busy ? <Badge tone="info">running</Badge> : error ? <Badge tone="error">failed</Badge> : suitability ? <Badge tone="ok">ranked</Badge> : land ? <Badge tone="info">land only</Badge> : undefined;
  const footer = <><button className="btn btn-sm btn-primary" onClick={onAssess} disabled={!canAssess || busy}>{busy ? "Assessing…" : suitability ? "Re-assess" : "Assess land & rank sites"}</button><span className="muted">reads Sentinel-2 · 60–90 s</span></>;
  return (
    <Panel title="Available land" meta={suitability ? `AHP · CR ${suitability.consistency_ratio.toFixed(3)}` : undefined} badge={badge} footer={footer} defaultOpen={false}>
      {busy && <Progress status={progress} label="queued" />}
      {error && !busy && <ErrorBox message={error} onRetry={onAssess} />}
      {!land && !busy && !error && <Empty>Run the assessment to find land that can be excavated and rank sites on the full criteria set.</Empty>}
      {land && !busy && (
        <>
          <p className="small">Eligible for excavation: <b>{land.total_eligible_area.display}</b> in {land.parcels.length} patches.</p>
          <details>
            <summary className="muted">Constraints applied ({land.constraints_applied.length})</summary>
            <ul className="muted small">{land.constraints_applied.map((c) => <li key={c}>{c}</li>)}</ul>
          </details>
          <table className="table">
            <thead><tr><th>Patch</th><th className="num">Area</th><th>Cover</th><th className="num">Slope</th><th>Ownership</th></tr></thead>
            <tbody>
              {land.parcels.slice(0, 6).map((p, i) => (
                <tr key={p.parcel_id}><td>{i + 1}</td><td className="num">{p.area.display?.split(" (")[0]}</td><td>{p.lulc_class}</td><td className="num">{p.mean_slope.value.toFixed(1)} %</td><td>{p.ownership_class}</td></tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {suitability && !busy && (
        <>
          <p className="small"><b>Ranked sites</b> · weights {Object.entries(suitability.weights).map(([k, v]) => `${k} ${v.toFixed(2)}`).join(" · ")} · CR {suitability.consistency_ratio.toFixed(3)} {suitability.consistency_acceptable ? "✓" : "✗"}</p>
          <div>
            {suitability.sites.map((s) => (
              <div key={s.rank} className="site" role="button" tabIndex={0} onClick={() => onPick(s)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onPick(s); }} title="Delineate this site's catchment">
                <span className="rank">{s.rank}</span>
                <div>
                  <div className="small">{s.catchment_area.display?.split(" (")[0]} upstream · {s.estimated_storage.display?.split(" (")[0]}</div>
                  <div className="bars" style={{ gridTemplateColumns: `repeat(${s.criteria.length}, 1fr)` }}>
                    {s.criteria.map((c) => <i key={c.criterion} title={`${c.criterion}: raw ${c.raw_value.display}, score ${c.normalised_score.value.toFixed(2)} × weight ${c.weight.value.toFixed(2)} = ${c.contribution.value.toFixed(3)}`}><b style={{ width: `${c.normalised_score.value * 100}%` }} /></i>)}
                  </div>
                </div>
                <span className="score">{s.total_score.value.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </>
      )}
      <Warnings items={(land?.warnings ?? []).concat(suitability?.warnings ?? []).filter((w) => w.code !== "ahp_matrix")} />
    </Panel>
  );
}
