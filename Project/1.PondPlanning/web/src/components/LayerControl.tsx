import type { LayerDescriptor } from "../types";

interface Props {
  layers: LayerDescriptor[];
  visible: Record<string, boolean>;
  onToggle: (id: string) => void;
  contourInterval: number;
  onInterval: (m: number) => void;
}

const EXTRA = [
  { id: "catchment", title: "Catchment", source: "D8 upstream of the clicked point" },
  { id: "sites", title: "Suggested sites", source: "terrain siting score" },
  { id: "boundary", title: "Area boundary", source: "from the upload" },
];

/** Layer toggles — FR8's overlay list, fed by GET /terrain/{id}/layers. */
export function LayerControl({ layers, visible, onToggle, contourInterval, onInterval }: Props) {
  const rows = [...layers.map((l) => ({ id: l.layer_id, title: l.title, source: l.source })), ...EXTRA];
  return (
    <section className="panel">
      <h2>Layers</h2>
      <ul className="layers">
        {rows.map((row) => (
          <li key={row.id}>
            <label>
              <input type="checkbox" checked={visible[row.id] ?? false} onChange={() => onToggle(row.id)} />
              {row.title}
              {row.id === "contours" && (
                <select value={contourInterval} onChange={(e) => onInterval(Number(e.target.value))} aria-label="Contour interval" className="inline">
                  {[1, 2, 5, 10].map((m) => (
                    <option key={m} value={m}>{m} m</option>
                  ))}
                </select>
              )}
            </label>
            <small className="muted">{row.source}</small>
          </li>
        ))}
      </ul>
    </section>
  );
}
