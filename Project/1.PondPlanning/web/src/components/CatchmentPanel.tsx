import type { CatchmentResult, JobStatus, QuantityOut } from "../types";

function Q({ q }: { q: QuantityOut }) {
  return <strong title={q.method ?? undefined}>{q.display ?? `${q.value} ${q.unit}`}</strong>;
}

/** FR4: the delineated catchment, with the snap distance front and centre. */
export function Progress({ status }: { status: JobStatus | null }) {
  if (!status) return null;
  return (
    <div className="job job-running" aria-live="polite">
      <div className="bar"><div className="fill" style={{ width: `${status.progress}%` }} /></div>
      <span>{status.progress}% {status.stage ? `· ${status.stage}` : ""}</span>
    </div>
  );
}

export function CatchmentPanel({ catchment, busy, error, progress }: { catchment: CatchmentResult | null; busy: boolean; error: string | null; progress: JobStatus | null }) {
  return (
    <section className="panel">
      <h2>Catchment</h2>
      {!catchment && !busy && !error && <p className="muted">Click anywhere on the map to delineate the area draining to that point.</p>}
      {busy && <Progress status={progress ?? { job_id: "", kind: "catchment", status: "running", progress: 5, stage: "submitting", created_at: new Date().toISOString() }} />}
      {error && <p className="error">{error}</p>}
      {catchment && (
        <>
          <dl>
            <dt>Area</dt>
            <dd><Q q={catchment.area} /></dd>
            <dt>Snap distance</dt>
            <dd><Q q={catchment.snap_distance} /></dd>
            <dt>Longest flow path</dt>
            <dd><Q q={catchment.longest_flow_path} /></dd>
            <dt>Mean slope</dt>
            <dd><Q q={catchment.mean_slope} /></dd>
            <dt>Relief</dt>
            <dd><Q q={catchment.relief} /></dd>
            <dt>Outlet elevation</dt>
            <dd><Q q={catchment.outlet_elevation} /></dd>
            <dt>Routing</dt>
            <dd className="muted">{catchment.flow_routing}</dd>
          </dl>
          {catchment.warnings.map((w) => (
            <p key={w.code} className={`warn warn-${w.severity}`}>{w.message}</p>
          ))}
        </>
      )}
    </section>
  );
}
