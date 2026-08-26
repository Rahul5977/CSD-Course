import { useCallback, useState } from "react";
import type { Progress } from "../api";
import type { JobStatus } from "../types";

/**
 * One asynchronous analysis as the UI sees it: its result, whether it is running,
 * its error, and the live job progress. Replaces four `useState`s per analysis.
 */
export function useTask<T>() {
  const [value, setValue] = useState<T | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<JobStatus | null>(null);

  const onProgress: Progress = useCallback((status) => {
    setProgress(status.status === "queued" || status.status === "running" ? status : null);
  }, []);

  /** Run `fn`; it receives the progress callback to pass into the API client. */
  const run = useCallback(async (fn: (onProgress: Progress) => Promise<T>) => {
    setBusy(true);
    setError(null);
    try {
      setValue(await fn(onProgress));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }, [onProgress]);

  const reset = useCallback(() => { setValue(null); setError(null); setProgress(null); }, []);
  return { value, busy, error, progress, run, set: setValue, reset };
}
