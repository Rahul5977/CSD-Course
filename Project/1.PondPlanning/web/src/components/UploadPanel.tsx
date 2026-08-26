import { useRef, useState } from "react";
import { api } from "../api";
import type { JobStatus } from "../types";
import { Badge, Callout, Panel, Progress } from "../ui";

interface Props {
  job: JobStatus | null;
  onSubmitted: (jobId: string) => void;
  hasVillages: boolean;
}

/** Phase 2 entry point: upload a KML/KMZ contour map and watch the job. */
export function UploadPanel({ job, onSubmitted, hasVillages }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState<string | null>(null);

  const submit = async () => {
    const file = input.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      onSubmitted((await api.uploadContour(file)).job_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const running = job && (job.status === "queued" || job.status === "running");
  const badge = running ? <Badge tone="info">running</Badge> : job?.status === "succeeded" ? <Badge tone="ok">analysed</Badge> : job?.status === "failed" ? <Badge tone="error">failed</Badge> : undefined;

  return (
    <Panel title="Contour map" badge={badge} defaultOpen={!hasVillages || !!job}>
      <p className="muted">{hasVillages ? "Upload another KML/KMZ to analyse a new area." : "Upload a KML or KMZ. Everything on the map is derived from it."}</p>
      <div className="row">
        <input ref={input} type="file" accept=".kml,.kmz" aria-label="Contour map file" onChange={(e) => setName(e.target.files?.[0]?.name ?? null)} style={{ display: "none" }} id="contour-file" />
        <label htmlFor="contour-file" className="btn btn-sm btn-secondary">{name ?? "Choose file…"}</label>
        <button className="btn btn-sm btn-primary" onClick={submit} disabled={busy || !!running || !name}>{busy ? "Uploading…" : "Analyse"}</button>
      </div>
      {error && <Callout tone="critical"><b>Upload failed</b> — {error}</Callout>}
      {job && (running || job.status === "failed") && <Progress status={job} />}
      {job?.error && <Callout tone="critical"><b>{job.error.code}</b> — {job.error.title}</Callout>}
    </Panel>
  );
}
