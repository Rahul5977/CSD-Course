import type { QuantityOut, VillageSummary } from "../types";

function Q({ q }: { q: QuantityOut }) {
  return <strong title={q.method ?? undefined}>{q.display ?? `${q.value} ${q.unit}`}</strong>;
}

/** FR1 headline card. Every number arrives with its unit and band; none is formatted here. */
export function SummaryCard({ summary }: { summary: VillageSummary }) {
  const v = summary.village;
  return (
    <section className="panel">
      <h2>{v.name}</h2>
      <p className="muted">
        {[v.district, v.state_code].filter(Boolean).join(", ") || "location from upload"} · EPSG:{v.utm_epsg}
      </p>
      <dl>
        <dt>Area</dt>
        <dd><Q q={v.area} /></dd>
        <dt>Elevation</dt>
        <dd>
          <Q q={summary.elevation.minimum} /> – <Q q={summary.elevation.maximum} />
        </dd>
        <dt>Relief</dt>
        <dd><Q q={summary.elevation.relief} /></dd>
        <dt>Mean slope</dt>
        <dd><Q q={summary.mean_slope} /></dd>
        <dt>DEM</dt>
        <dd>{summary.dem_source}</dd>
        <dt>Vertical accuracy</dt>
        <dd><Q q={summary.dem_vertical_accuracy} /></dd>
      </dl>
      {summary.warnings.map((w) => (
        <p key={w.code} className={`warn warn-${w.severity}`}>{w.message}</p>
      ))}
    </section>
  );
}
