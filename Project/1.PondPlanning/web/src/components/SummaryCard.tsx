import type { VillageSummary } from "../types";
import { Panel, Qty, Warnings } from "../ui";

/** FR1 headline card. Every number arrives with its unit and band; none is invented here. */
export function SummaryCard({ summary }: { summary: VillageSummary }) {
  const v = summary.village;
  return (
    <Panel title="Area" meta={`EPSG:${v.utm_epsg}`}>
      <p className="muted">{[v.district, v.state_code].filter(Boolean).join(", ") || "location from the upload"}</p>
      <div className="qty-grid">
        <Qty q={v.area} label="Area" note="upload extent" />
        <Qty q={summary.elevation.relief} label="Relief" note={`${summary.elevation.minimum.value.toFixed(0)}–${summary.elevation.maximum.value.toFixed(0)} m`} />
        <Qty q={summary.mean_slope} label="Mean slope" note="Horn 1981" />
      </div>
      <p className="small"><span className="muted">DEM</span> {summary.dem_source} · vertical accuracy <b>{summary.dem_vertical_accuracy.display ?? `${summary.dem_vertical_accuracy.value} ${summary.dem_vertical_accuracy.unit}`}</b></p>
      <Warnings items={summary.warnings} />
    </Panel>
  );
}
