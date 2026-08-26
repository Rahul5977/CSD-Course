import { useRef, useState } from "react";
import { api } from "../api";
import type { JobStatus } from "../types";

interface Props {
  job: JobStatus | null;
  onSubmitted: (jobId: string) => void;
}

/** FR-Phase 2 entry point: upload a KML/KMZ contour map and watch the job. */
export function UploadPanel({ job, onSubmitted }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    const file = input.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const accepted = await api.uploadContour(file);
      onSubmitted(accepted.job_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const running = job && (job.status === "queued" || job.status === "running");

  return (
    <section className="panel">
      <h2>Contour map</h2>
      <p className="muted">Upload a KML or KMZ. Everything on the map is derived from it.</p>
      <div className="row">
        <input ref={input} type="file" accept=".kml,.kmz" aria-label="Contour map file" />
        <button onClick={submit} disabled={busy || !!running}>
          {busy ? "Uploading…" : "Analyse"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {job && (
        <div className={`job job-${job.status}`} aria-live="polite">
          <div className="bar">
            <div className="fill" style={{ width: `${job.progress}%` }} />
          </div>
          <span>
            {job.status} · {job.progress}% {job.stage ? `· ${job.stage}` : ""}
          </span>
          {job.error && (
            <p className="error">
              {job.error.code}: {job.error.title}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
