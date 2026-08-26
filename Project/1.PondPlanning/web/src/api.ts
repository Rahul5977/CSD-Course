import type { RainfallStatistics } from "./components/RainfallPanel";
import type { PondDesignResult } from "./components/WaterPanel";
import type { AvailableLand, SuitabilityResult } from "./components/LandPanel";
import type {
  CatchmentResult,
  ContourAnalysisResult,
  ContourResponse,
  JobAccepted,
  JobStatus,
  LayerDescriptor,
  Page,
  PourPoint,
  StreamNetwork,
  VillageOut,
  VillageSummary,
} from "./types";

const BASE = "/api/v1";

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const problem = await response.json();
      detail = problem.title ?? problem.code ?? detail;
    } catch {
      /* not a problem document */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

/** Poll a job until it settles; resolves with the final status. */
export async function waitForJob(jobId: string, intervalMs = 800, maxMs = 120_000): Promise<JobStatus> {
  const started = Date.now();
  for (;;) {
    const status = await api.job(jobId);
    if (status.status !== "queued" && status.status !== "running") return status;
    if (Date.now() - started > maxMs) throw new Error("job timed out");
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

export const api = {
  uploadContour(file: File): Promise<JobAccepted> {
    const body = new FormData();
    body.append("file", file);
    return fetch(`${BASE}/analyzeContour`, { method: "POST", body }).then(json<JobAccepted>);
  },
  job(id: string): Promise<JobStatus> {
    return fetch(`${BASE}/jobs/${id}`).then(json<JobStatus>);
  },
  contourResult(jobId: string): Promise<ContourAnalysisResult> {
    return fetch(`${BASE}/analysis/results/contour/${jobId}`).then(json<ContourAnalysisResult>);
  },
  villages(): Promise<Page<VillageOut>> {
    return fetch(`${BASE}/villages?limit=50`).then(json<Page<VillageOut>>);
  },
  summary(id: string): Promise<VillageSummary> {
    return fetch(`${BASE}/villages/${id}/summary`).then(json<VillageSummary>);
  },
  layers(id: string): Promise<{ layers: LayerDescriptor[] }> {
    return fetch(`${BASE}/terrain/${id}/layers`).then(json<{ layers: LayerDescriptor[] }>);
  },
  contours(id: string, interval: number): Promise<ContourResponse> {
    return fetch(`${BASE}/terrain/${id}/contours?interval=${interval}`).then(json<ContourResponse>);
  },
  streams(id: string): Promise<StreamNetwork> {
    return fetch(`${BASE}/terrain/${id}/streams`).then(json<StreamNetwork>);
  },
  async catchment(villageId: string, point: PourPoint): Promise<CatchmentResult> {
    const accepted = await fetch(`${BASE}/analysis/catchment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ village_id: villageId, pour_point: point }),
    }).then(json<JobAccepted>);
    const status = await waitForJob(accepted.job_id);
    if (status.status !== "succeeded") throw new Error(status.error?.title ?? `job ${status.status}`);
    return fetch(`${BASE}/analysis/results/catchment/${accepted.job_id}`).then(json<CatchmentResult>);
  },
  async pondDesign(villageId: string, point: PourPoint, targetReliability = 0.75): Promise<PondDesignResult> {
    const accepted = await fetch(`${BASE}/analysis/pond-design`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ village_id: villageId, pour_point: point, target_reliability: targetReliability }),
    }).then(json<JobAccepted>);
    const status = await waitForJob(accepted.job_id, 1000, 300_000);
    if (status.status !== "succeeded") throw new Error(status.error?.title ?? `job ${status.status}`);
    return fetch(`${BASE}/analysis/results/pond-design/${accepted.job_id}`).then(json<PondDesignResult>);
  },
  async suitability(villageId: string, topN = 8): Promise<SuitabilityResult> {
    const accepted = await fetch(`${BASE}/analysis/suitability`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ village_id: villageId, top_n: topN }),
    }).then(json<JobAccepted>);
    const status = await waitForJob(accepted.job_id, 1500, 600_000);
    if (status.status !== "succeeded") throw new Error(status.error?.title ?? `job ${status.status}`);
    return fetch(`${BASE}/analysis/results/suitability/${accepted.job_id}`).then(json<SuitabilityResult>);
  },
  availableLand(villageId: string): Promise<AvailableLand | null> {
    return fetch(`${BASE}/villages/${villageId}/available-land`).then((r) => (r.ok ? r.json() : null));
  },
  rainfallStatistics(lon: number, lat: number): Promise<RainfallStatistics> {
    return fetch(`${BASE}/rainfall/statistics?lon=${lon}&lat=${lat}`).then(json<RainfallStatistics>);
  },
  /** The latest contour-analysis result for a village, if the session knows one. */
  siting(id: string): Promise<{ candidate_sites: ContourAnalysisResult["candidate_sites"]; siting: ContourAnalysisResult["siting"] } | null> {
    return fetch(`${BASE}/villages/${id}/siting`).then((r) => (r.ok ? r.json() : null));
  },
};
