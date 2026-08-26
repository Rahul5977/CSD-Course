import type { LayerDescriptor } from "../types";

interface Props {
  layers: LayerDescriptor[];
  visible: Record<string, boolean>;
  onToggle: (id: string) => void;
}

/** Layer toggles — FR8's overlay list, fed by GET /terrain/{id}/layers. */
export function LayerControl({ layers, visible, onToggle }: Props) {
  const rows = [
    ...layers.map((l) => ({ id: l.layer_id, title: l.title, source: l.source })),
    { id: "boundary", title: "Area boundary", source: "from the upload" },
  ];
  return (
    <section className="panel">
      <h2>Layers</h2>
      <ul className="layers">
        {rows.map((row) => (
          <li key={row.id}>
            <label>
              <input
                type="checkbox"
                checked={visible[row.id] ?? true}
                onChange={() => onToggle(row.id)}
              />
              {row.title}
            </label>
            <small className="muted">{row.source}</small>
          </li>
        ))}
      </ul>
    </section>
  );
}
