import type { QuantityOut, ResultWarning } from "../types";
import { Badge, Empty, ErrorBox, Panel, Qty, Q, Skeleton, Warnings } from "../ui";

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
  warnings: ResultWarning[];
}

const MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "J", "N", "D"];

/** FR5: rainfall statistics with an inline SVG monthly chart. No chart library. */
export function RainfallPanel({ stats, busy, error, onRetry }: { stats: RainfallStatistics | null; busy: boolean; error: string | null; onRetry?: () => void }) {
  const max = stats ? Math.max(...stats.monthly_normals.map((m) => m.mean_rainfall.value), 1) : 1;
  const W = 320, H = 110, pad = 18;
  const badge = busy ? <Badge tone="info">fetching</Badge> : error ? <Badge tone="error">failed</Badge>
    : stats?.fallback_used === "cache" ? <Badge tone="stale">cached</Badge>
    : stats?.fallback_used === "secondary_provider" ? <Badge tone="warn">fallback provider</Badge>
    : stats ? <Badge tone="ok">{stats.years_of_record} yr</Badge> : undefined;
  return (
    <Panel title="Rainfall" badge={badge} meta={stats ? `${stats.start_year}–${stats.end_year}` : undefined}>
      {busy && !stats && <Skeleton lines={4} />}
      {error && !busy && <ErrorBox message={error} onRetry={onRetry} />}
      {!busy && !error && !stats && <Empty>Select an analysed area to fetch its rainfall record.</Empty>}
      {stats && (
        <>
          <Qty q={stats.dependable_75} label="In 3 of every 4 years, at least" size="lg" note={`75 % dependable · ${stats.years_of_record} complete years`} />
          <div className="qty-grid">
            <Qty q={stats.mean_annual} label="Mean annual" />
            <Qty q={stats.monsoon_share} label="Monsoon share" />
            <Qty q={stats.rainy_days_mean} label="Rainy days" />
          </div>
          <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Monthly mean rainfall">
            {stats.monthly_normals.map((m, i) => {
              const bw = (W - 2 * pad) / 12;
              const h = ((H - 2 * pad) * m.mean_rainfall.value) / max;
              return (
                <g key={m.month}>
                  <rect x={pad + i * bw + 2} y={H - pad - h} width={bw - 4} height={h} fill={m.month >= 6 && m.month <= 9 ? "#0b6e8f" : "#9cc3d3"}>
                    <title>{`${m.mean_rainfall.display} · ${m.rainy_days.value.toFixed(0)} rainy days`}</title>
                  </rect>
                  <text x={pad + i * bw + bw / 2} y={H - 4} fontSize="9" textAnchor="middle" fill="#5b6770">{MONTHS[i]}</text>
                </g>
              );
            })}
            <text x={pad} y={12} fontSize="9" fill="#5b6770">mm / month · {stats.years_of_record}-yr mean · Jun–Sep in blue</text>
          </svg>
          <p className="small"><span className="muted">Variability</span> CV <Q q={stats.coefficient_of_variation} /> · <span className="muted">max 1-day</span> <Q q={stats.max_daily_recorded} /></p>
          {stats.fallback_used === "cache" && <div className="callout callout-warn">Served from cache — the rainfall provider was unreachable. Values are unchanged since the last refresh.</div>}
          <p className="muted">{stats.source} · {stats.attribution}</p>
          <Warnings items={stats.warnings} />
        </>
      )}
    </Panel>
  );
}
