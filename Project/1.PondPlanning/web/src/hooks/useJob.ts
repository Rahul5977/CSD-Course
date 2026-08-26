import { useEffect, useState } from "react";
import { api } from "../api";
import type { JobStatus } from "../types";

/** Poll /jobs/{id} until it settles. The 202 → poll pattern, in one hook. */
export function useJob(jobId: string | null, intervalMs = 1500) {
  const [status, setStatus] = useState<JobStatus | null>(null);

  useEffect(() => {
    if (!jobId) {
      setStatus(null);
      return;
    }
    let cancelled = false;
    const tick = async () => {
      try {
        const next = await api.job(jobId);
        if (cancelled) return;
        setStatus(next);
        if (next.status === "queued" || next.status === "running") {
          timer = window.setTimeout(tick, intervalMs);
        }
      } catch (error) {
        if (!cancelled) {
          setStatus({
            job_id: jobId,
            kind: "unknown",
            status: "failed",
            progress: 0,
            stage: null,
            error: { code: "network", title: (error as Error).message },
            result_url: null,
          });
        }
      }
    };
    let timer = window.setTimeout(tick, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [jobId, intervalMs]);

  return status;
}
