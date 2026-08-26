import type { SiteCandidate, SitingMethod } from "../types";
import { Panel } from "../ui";

interface Props {
  sites: SiteCandidate[];
  method: SitingMethod | null;
  rationale: string | null;
  onPick: (site: SiteCandidate) => void;
}

const ORDER = ["upstream_area", "flatness", "wetness", "impoundment"];

/** Ranked pond sites from the terrain-only siting engine, with per-criterion score bars. */
export function SitesPanel({ sites, method, rationale, onPick }: Props) {
  if (!sites.length) return null;
  return (
    <Panel title="Suggested sites" meta={method ? `AHP · CR ${(method as unknown as { consistency_ratio?: number }).consistency_ratio?.toFixed(3) ?? ""}`.replace(/ · CR $/, "") : undefined}>
      {rationale && <p className="muted">{rationale}</p>}
      <div>
        {sites.map((s) => (
          <div key={s.rank} className="site" role="button" tabIndex={0} onClick={() => onPick(s)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onPick(s); }} title="Delineate this site's catchment">
            <span className="rank">{s.rank}</span>
            <div>
              <div className="small">Upstream {s.upstream_area.display?.split(" (")[0] ?? `${s.upstream_area.value} ${s.upstream_area.unit}`} · slope {s.local_slope.value.toFixed(1)} % · TWI {s.wetness_index.value.toFixed(1)}</div>
              <div className="bars" aria-label="criterion scores">
                {ORDER.map((k) => <i key={k} title={`${k}: ${((s.criteria as Record<string, number>)[k] * 100).toFixed(0)} %`}><b style={{ width: `${((s.criteria as Record<string, number>)[k] ?? 0) * 100}%` }} /></i>)}
              </div>
            </div>
            <span className="score">{s.score.value.toFixed(2)}</span>
          </div>
        ))}
      </div>
      <p className="muted">Bars: upstream area · flatness · wetness · impoundment. Click a site to delineate its catchment.</p>
      {method && (
        <details>
          <summary className="muted">How sites are ranked</summary>
          <p className="muted">{method.description}</p>
          <p className="muted">weights {Object.entries(method.weights).map(([k, v]) => `${k} ${v}`).join(" · ")} · channels ≥ {method.stream_threshold.display} · slope ≤ {method.max_slope.display} · {method.candidates_considered} cells considered</p>
        </details>
      )}
    </Panel>
  );
}
