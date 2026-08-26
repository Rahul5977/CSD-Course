import type { QuantityOut } from "../types";

export interface MonthlyNormal {
  month: number;
  mean_rainfall: QuantityOut;
  rainy_days: QuantityOut;
}

export interface RainfallStatistics {
  source: string;
  years_of_record: number;
  start_year: number;
  end_year: number;
  mean_annual: QuantityOut;
  median_annual: QuantityOut;
  dependable_75: QuantityOut;
  coefficient_of_variation: QuantityOut;
  monsoon_share: QuantityOut;
  max_daily_recorded: QuantityOut;
  rainy_days_mean: QuantityOut;
  monthly_normals: MonthlyNormal[];
  data_completeness: QuantityOut;
  fallback_used: "none" | "cache" | "secondary_provider";
  attribution: string;
  warnings: { code: string; message: string; severity: string }[];
}

const MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

function Q({ q }: { q: QuantityOut }) {
  return <strong title={q.method ?? undefined}>{q.display ?? `${q.value} ${q.unit}`}</strong>;
}

/** FR5: rainfall statistics card with an inline SVG monthly chart. No chart library. */
export function RainfallPanel({ stats, busy, error }: { stats: RainfallStatistics | null; busy: boolean; error: string | null }) {
  const max = stats ? Math.max(...stats.monthly_normals.map((m) => m.mean_rainfall.value), 1) : 1;
  const W = 300, H = 110, pad = 18;
  return (
    <section className="panel">
      <h2>Rainfall</h2>
      {busy && <p className="muted" aria-live="polite">Fetching the daily record…</p>}
      {error && <p className="error">{error}</p>}
      {stats && (
        <>
          <p className="muted">
            {stats.source} · {stats.start_year}–{stats.end_year} ({stats.years_of_record} yr)
            {stats.fallback_used !== "none" && <span className="badge-stale"> {stats.fallback_used === "cache" ? "cached — live API unreachable" : "secondary provider"}</span>}
          </p>
          <p className="verdict">In 3 of every 4 years, expect at least <Q q={stats.dependable_75} />.</p>
          <dl>
            <dt>Mean annual</dt>
            <dd><Q q={stats.mean_annual} /></dd>
            <dt>75 % dependable</dt>
            <dd><Q q={stats.dependable_75} /></dd>
            <dt>Variability (CV)</dt>
            <dd><Q q={stats.coefficient_of_variation} /></dd>
            <dt>Monsoon (Jun–Sep)</dt>
            <dd><Q q={stats.monsoon_share} /></dd>
            <dt>Rainy days (≥ 2.5 mm)</dt>
            <dd><Q q={stats.rainy_days_mean} /></dd>
            <dt>Max 1-day</dt>
            <dd><Q q={stats.max_daily_recorded} /></dd>
          </dl>
          <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Monthly mean rainfall">
            {stats.monthly_normals.map((m, i) => {
              const bw = (W - 2 * pad) / 12;
              const h = ((H - 2 * pad) * m.mean_rainfall.value) / max;
              return (
                <g key={m.month}>
                  <rect x={pad + i * bw + 2} y={H - pad - h} width={bw - 4} height={h} fill={m.month >= 6 && m.month <= 9 ? "#0b6e8f" : "#8fb8c9"}>
                    <title>{`${m.mean_rainfall.display} · ${m.rainy_days.value.toFixed(0)} rainy days`}</title>
                  </rect>
                  <text x={pad + i * bw + bw / 2} y={H - 4} fontSize="9" textAnchor="middle" fill="#5b6770">{MONTHS[i]}</text>
                </g>
              );
            })}
            <text x={pad} y={12} fontSize="9" fill="#5b6770">mm / month, {stats.years_of_record}-yr mean</text>
          </svg>
          <p className="muted">{stats.attribution}</p>
          {stats.warnings.map((w) => (
            <p key={w.code} className={`warn warn-${w.severity}`}>{w.message}</p>
          ))}
        </>
      )}
    </section>
  );
}
