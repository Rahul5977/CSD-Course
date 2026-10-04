import type { CatchmentResult, JobStatus } from "../types";
import { Badge, Empty, ErrorBox, Facts, Panel, Progress, Q, Qty, Warnings } from "../ui";

export { Progress } from "../ui";

/** FR4: the delineated catchment, with the snap distance front and centre. */
export function CatchmentPanel({ catchment, busy, error, progress, onDesign, designBusy, onRetry }: {
  catchment: CatchmentResult | null; busy: boolean; error: string | null; progress: JobStatus | null;
  onDesign?: () => void; designBusy?: boolean; onRetry?: () => void;
}) {
  const badge = busy ? <Badge tone="info">running</Badge> : error ? <Badge tone="error">failed</Badge> : catchment ? <Badge tone="ok">done</Badge> : undefined;
  const footer = catchment && onDesign ? (
    <>
      <button className="btn btn-sm btn-primary" onClick={onDesign} disabled={designBusy}>{designBusy ? "Designing…" : "Design a pond here"}</button>
      <span className="muted">rainfall → runoff → storage</span>
    </>
  ) : undefined;
  return (
    <Panel title="Catchment" badge={badge} footer={footer}>
      {!catchment && !busy && !error && <Empty>Click anywhere on the map, or pick a suggested site, to delineate the area that drains to it.</Empty>}
      {busy && (
        <>
          <Progress status={progress} label="submitting" />
          <span className="muted">interactive queue · usually a few seconds</span>
        </>
      )}
      {error && !busy && <ErrorBox message={error} onRetry={onRetry} />}
      {catchment && !busy && (
        <>
          <Qty q={catchment.area} label="Area draining to the point" size="lg" note={catchment.flow_routing} />
          <Facts rows={[
            ["Snapped", <><Q q={catchment.snap_distance} /> to the nearest channel</>],
            ["Longest flow path", <Q q={catchment.longest_flow_path} />],
            ["Mean slope", <Q q={catchment.mean_slope} />],
            ["Relief", <><Q q={catchment.relief} /> · outlet <Q q={catchment.outlet_elevation} /></>],
          ]} />
          <Warnings items={catchment.warnings} />
        </>
      )}
    </Panel>
  );
}
