import type {
  JobAccepted,
  JobStatus,
  LayerDescriptor,
  Page,
  TerrainPreparationResult,
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

export const api = {
  uploadContour(file: File): Promise<JobAccepted> {
    const body = new FormData();
    body.append("file", file);
    return fetch(`${BASE}/analyzeContour`, { method: "POST", body }).then(json<JobAccepted>);
  },
  job(id: string): Promise<JobStatus> {
    return fetch(`${BASE}/jobs/${id}`).then(json<JobStatus>);
  },
  jobResult<T>(id: string): Promise<T> {
    return fetch(`${BASE}/jobs/${id}/result`)
      .then(json<{ result: T }>)
      .then((r) => r.result);
  },
  villages(): Promise<Page<VillageOut>> {
    return fetch(`${BASE}/villages?limit=50`).then(json<Page<VillageOut>>);
  },
  village(id: string): Promise<VillageOut> {
    return fetch(`${BASE}/villages/${id}`).then(json<VillageOut>);
  },
  summary(id: string): Promise<VillageSummary> {
    return fetch(`${BASE}/villages/${id}/summary`).then(json<VillageSummary>);
  },
  layers(id: string): Promise<{ layers: LayerDescriptor[] }> {
    return fetch(`${BASE}/terrain/${id}/layers`).then(json<{ layers: LayerDescriptor[] }>);
  },
  terrainResult(jobId: string): Promise<TerrainPreparationResult> {
    return api.jobResult<TerrainPreparationResult>(jobId);
  },
};
