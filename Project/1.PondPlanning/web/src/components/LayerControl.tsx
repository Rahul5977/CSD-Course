import type { LayerDescriptor } from "../types";
import { Panel } from "../ui";

interface Props {
  layers: LayerDescriptor[];
  visible: Record<string, boolean>;
  onToggle: (id: string) => void;
  contourInterval: number;
  onInterval: (m: number) => void;
}

const EXTRA = [
  { id: "pond", title: "Designed pond footprint", source: "FR7 dimensions at the outlet" },
  { id: "focus", title: "Dim outside the boundary", source: "imagery clipped to the analysed area" },
  { id: "available_land", title: "Available land (FR3)", source: "Specification constraints" },
  { id: "catchment", title: "Catchment", source: "D8 upstream of the clicked point" },
  { id: "sites", title: "Suggested sites", source: "terrain siting score" },
  { id: "boundary", title: "Area boundary", source: "from the upload" },
];
const SWATCH: Record<string, string> = { satellite: "#3b5b3b", hillshade: "#8c8c8c", dem: "#c8a165", slope: "#5b3f8f", twi: "#2f6f8f", streams: "#1e90ff", contours: "#d8b46a", catchment: "#0b6e8f", sites: "#2f7d32", boundary: "#e5c04b", pond: "#0b6e8f", available_land: "#8a5a2b", focus: "#1b262c" };

/** Layer toggles — FR8's overlay list, fed by GET /terrain/{id}/layers. */
export function LayerControl({ layers, visible, onToggle, contourInterval, onInterval }: Props) {
  const rows = [...layers.map((l) => ({ id: l.layer_id, title: l.title, source: l.source })), ...EXTRA];
  const on = rows.filter((r) => visible[r.id]).length;
  return (
    <Panel title="Layers" meta={`${on} of ${rows.length} on`} defaultOpen={false}>
      <div>
        {rows.map((row) => (
          <label key={row.id} className="layer">
            <input type="checkbox" checked={visible[row.id] ?? false} onChange={() => onToggle(row.id)} />
            <span className="sw" style={{ background: SWATCH[row.id] ?? "#999" }} />
            <span className="name" title={row.source}>{row.title}</span>
            {row.id === "contours" && (
              <select value={contourInterval} onChange={(e) => onInterval(Number(e.target.value))} aria-label="Contour interval" className="inline">
                {[1, 2, 5, 10].map((m) => <option key={m} value={m}>{m} m</option>)}
              </select>
            )}
          </label>
        ))}
      </div>
    </Panel>
  );
}
