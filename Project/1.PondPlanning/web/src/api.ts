import type {
  AvailableLand,
  PondDesignResult,
  RainfallStatistics,
  RecommendationOut,
  Session,
  SuitabilityResult,
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

/** Set by the service worker when a response came from cache because the network failed. */
export const staleState = { stale: false, listeners: new Set<(stale: boolean) => void>() };
function noteStale(response: Response) {
  const stale = response.headers.get("X-From-Cache") === "true";
  if (stale !== staleState.stale) {
    staleState.stale = stale;
    staleState.listeners.forEach((fn) => fn(stale));
  }
}

async function json<T>(response: Response): Promise<T> {
  noteStale(response);
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
export type Progress = (status: JobStatus) => void;

/** A fresh Idempotency-Key per user action: a double-tap must not queue two jobs. */
const idem = () => ({ "Idempotency-Key": crypto.randomUUID() });

/** Try the WebSocket first (one frame per change); fall back to polling. */
function watchSocket(jobId: string, onProgress?: Progress): Promise<JobStatus | null> {
  return new Promise((resolve) => {
    let settled = false;
    let socket: WebSocket;
    try {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${proto}://${location.host}${BASE}/jobs/${jobId}/ws`);
    } catch {
      resolve(null);
      return;
    }
    socket.onmessage = (event) => {
      const status = JSON.parse(event.data) as JobStatus;
      onProgress?.(status);
      if (status.status !== "queued" && status.status !== "running") { settled = true; resolve(status); socket.close(); }
    };
    socket.onerror = () => { if (!settled) { settled = true; resolve(null); } };
    socket.onclose = () => { if (!settled) { settled = true; resolve(null); } };
  });
}

export async function waitForJob(jobId: string, intervalMs = 800, maxMs = 120_000, onProgress?: Progress): Promise<JobStatus> {
  const viaSocket = await watchSocket(jobId, onProgress);
  if (viaSocket) return viaSocket;
  const started = Date.now();
  for (;;) {
    const status = await api.job(jobId);
    onProgress?.(status);
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
  async catchment(villageId: string, point: PourPoint, onProgress?: Progress): Promise<CatchmentResult> {
    const accepted = await fetch(`${BASE}/analysis/catchment`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...idem() },
      body: JSON.stringify({ village_id: villageId, pour_point: point }),
    }).then(json<JobAccepted>);
    const status = await waitForJob(accepted.job_id, 800, 120_000, onProgress);
    if (status.status !== "succeeded") throw new Error(status.error?.title ?? `job ${status.status}`);
    return fetch(`${BASE}/analysis/results/catchment/${accepted.job_id}`).then(json<CatchmentResult>);
  },
  async pondDesign(villageId: string, point: PourPoint, targetReliability = 0.75, onProgress?: Progress): Promise<PondDesignResult> {
    const accepted = await fetch(`${BASE}/analysis/pond-design`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...idem() },
      body: JSON.stringify({ village_id: villageId, pour_point: point, target_reliability: targetReliability }),
    }).then(json<JobAccepted>);
    const status = await waitForJob(accepted.job_id, 1000, 300_000, onProgress);
    if (status.status !== "succeeded") throw new Error(status.error?.title ?? `job ${status.status}`);
    const design = await fetch(`${BASE}/analysis/results/pond-design/${accepted.job_id}`).then(json<PondDesignResult>);
    design.job_id = accepted.job_id;
    return design;
  },
  async login(username: string, password: string): Promise<Session> {
    const t = await fetch(`${BASE}/auth/token`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) }).then(json<{ access_token: string; role: string }>);
    return { username, role: t.role, token: t.access_token };
  },
  saveRecommendation(designJobId: string, token: string): Promise<RecommendationOut> {
    return fetch(`${BASE}/recommendations`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ design_job_id: designJobId }) }).then(json<RecommendationOut>);
  },
  changeStatus(id: string, status: string, reason: string, token: string): Promise<RecommendationOut> {
    return fetch(`${BASE}/recommendations/${id}/status`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ status, reason }) }).then(json<RecommendationOut>);
  },
  audit(id: string): Promise<{ audit: { actor: string; action: string; detail: Record<string, unknown> }[] }> {
    return fetch(`${BASE}/recommendations/${id}/audit`).then(json<{ audit: { actor: string; action: string; detail: Record<string, unknown> }[] }>);
  },
  createExport(id: string, fmt: string): Promise<{ url: string }> {
    return fetch(`${BASE}/recommendations/${id}/exports?export_format=${fmt}`, { method: "POST" }).then(json<{ url: string }>);
  },
  async suitability(villageId: string, topN = 8, onProgress?: Progress): Promise<SuitabilityResult> {
    const accepted = await fetch(`${BASE}/analysis/suitability`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...idem() },
      body: JSON.stringify({ village_id: villageId, top_n: topN }),
    }).then(json<JobAccepted>);
    const status = await waitForJob(accepted.job_id, 1500, 600_000, onProgress);
    if (status.status !== "succeeded") throw new Error(status.error?.title ?? `job ${status.status}`);
    return fetch(`${BASE}/analysis/results/suitability/${accepted.job_id}`).then(json<SuitabilityResult>);
  },
  availableLand(villageId: string): Promise<AvailableLand | null> {
    return fetch(`${BASE}/villages/${villageId}/available-land`).then((r) => (r.ok ? r.json() : null));
  },
  rainfallStatistics(lon: number, lat: number, years = 45): Promise<RainfallStatistics> {
    return fetch(`${BASE}/rainfall/statistics?lon=${lon}&lat=${lat}&years=${years}`).then(json<RainfallStatistics>);
  },
  /** The latest contour-analysis result for a village, if the session knows one. */
  siting(id: string): Promise<{ candidate_sites: ContourAnalysisResult["candidate_sites"]; siting: ContourAnalysisResult["siting"] } | null> {
    return fetch(`${BASE}/villages/${id}/siting`).then((r) => (r.ok ? r.json() : null));
  },
};
