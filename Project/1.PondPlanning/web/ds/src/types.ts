/** A measured or derived number as the Pond Planner API returns it: never a bare value. */
export interface Quantity {
  /** Numeric value in `unit`. */
  value: number;
  /** SI-style unit label shown small after the value, e.g. `ha`, `m³`, `mm/yr`. */
  unit: string;
  /** Symmetric uncertainty band in percent; shown as `±N %` beside the value. */
  uncertainty_pct?: number | null;
  /** Lower bound of the band, if the API computed one. */
  low?: number | null;
  /** Upper bound of the band, if the API computed one. */
  high?: number | null;
  /** Human-readable method or provenance; shown in the tooltip. */
  method?: string | null;
  /** Preformatted `value unit (±band)` string from the API; used in tooltips. */
  display?: string | null;
}

/** A warning attached to a result; severity picks the callout tone. */
export interface ResultWarning {
  code: string;
  message: string;
  severity: "info" | "caution" | "critical";
}

/** Live job state from `GET /jobs/{id}` or the job WebSocket. */
export interface JobState {
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  /** 0–100, real progress from the worker, never animated. */
  progress: number;
  /** Stage label from the pipeline, e.g. "delineating upstream cells". */
  stage?: string | null;
}
