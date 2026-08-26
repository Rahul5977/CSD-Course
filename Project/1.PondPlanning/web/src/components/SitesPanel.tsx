import type { SiteCandidate, SitingMethod } from "../types";

interface Props {
  sites: SiteCandidate[];
  method: SitingMethod | null;
  rationale: string | null;
  onPick: (site: SiteCandidate) => void;
}

/** Ranked pond sites from the terrain-only siting engine, with per-criterion scores. */
export function SitesPanel({ sites, method, rationale, onPick }: Props) {
  if (!sites.length) return null;
  return (
    <section className="panel">
      <h2>Suggested pond sites</h2>
      {rationale && <p className="muted">{rationale}</p>}
      <ol className="sites">
        {sites.map((s) => (
          <li key={s.rank}>
            <button className="linkish" onClick={() => onPick(s)} title="Delineate this site's catchment">
              #{s.rank} · score {s.score.value.toFixed(2)}
            </button>
            <small className="muted">
              {s.upstream_area.display} upstream · slope {s.local_slope.value.toFixed(1)} % · TWI {s.wetness_index.value.toFixed(1)} · {s.impoundment_volume.display} behind {method?.nominal_rise.display}
            </small>
            <div className="bars">
              {Object.entries(s.criteria).map(([k, v]) => (
                <span key={k} title={`${k}: ${(v * 100).toFixed(0)} %`} className="bar-mini"><i style={{ width: `${v * 100}%` }} />{k}</span>
              ))}
            </div>
          </li>
        ))}
      </ol>
      {method && (
        <details>
          <summary className="muted">How sites are ranked</summary>
          <p className="muted">{method.description}</p>
          <p className="muted">
            weights {Object.entries(method.weights).map(([k, v]) => `${k} ${v}`).join(" · ")} · channels ≥ {method.stream_threshold.display} · slope ≤ {method.max_slope.display} · {method.candidates_considered} cells considered
          </p>
        </details>
      )}
    </section>
  );
}
