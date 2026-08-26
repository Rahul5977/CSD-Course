import type { CatchmentResult, QuantityOut } from "../types";

function Q({ q }: { q: QuantityOut }) {
  return <strong title={q.method ?? undefined}>{q.display ?? `${q.value} ${q.unit}`}</strong>;
}

/** FR4: the delineated catchment, with the snap distance front and centre. */
export function CatchmentPanel({ catchment, busy, error }: { catchment: CatchmentResult | null; busy: boolean; error: string | null }) {
  return (
    <section className="panel">
      <h2>Catchment</h2>
      {!catchment && !busy && !error && <p className="muted">Click anywhere on the map to delineate the area draining to that point.</p>}
      {busy && <p className="muted" aria-live="polite">Tracing upstream cells…</p>}
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
