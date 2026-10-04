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

/**
 * fetch that survives a dropped connection. Retries only a *network* failure (fetch throws
 * TypeError: DNS, reset, timeout) — never an HTTP answer, which is the server's decision.
 * Safe for POSTs because every analysis POST carries an Idempotency-Key, and the retry
 * resends the same headers: a request that did arrive returns the original job.
 * Found on the lab deployment, where a laptop's route loses ~60 % of new connections.
 */
async function net(input: string, init?: RequestInit, attempts = 4): Promise<Response> {
  for (let attempt = 1; ; attempt++) {
    try {
      return await fetch(input, init);
    } catch (e) {
      if (!(e instanceof TypeError) || attempt >= attempts) {
        throw new Error("Network unreachable — check the connection and try again");
      }
      await new Promise((r) => setTimeout(r, 400 * 2 ** (attempt - 1)));
    }
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

/** A fresh Idempotency-Key per user action: a double-tap must not queue two jobs.
 * `crypto.randomUUID` exists only in secure contexts (HTTPS / localhost); a plain-HTTP
 * deployment (the lab VM by IP) needs the manual v4 fallback or every map click throws. */
const uuid = (): string =>
  typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
        (+c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (+c / 4)))).toString(16),
      );
const idem = () => ({ "Idempotency-Key": uuid() });

/** The server sends the current status the moment it accepts, so silence means a lost
 * handshake or a dead connection — not a slow job. */
const SOCKET_FIRST_FRAME_MS = 4_000;
const SOCKET_IDLE_MS = 15_000;

/** Try the WebSocket first (one frame per change); fall back to polling.
 * Watchdog: on a lossy route a dropped handshake fires neither onerror nor onclose for a
 * minute or more, which left the UI frozen at "submitting". No first frame within 4 s, or
 * 15 s of silence after it, closes the socket and hands over to polling. */
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
    let timer: ReturnType<typeof setTimeout> | undefined;
    const giveUp = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(null);
      socket.close();
    };
    const arm = (ms: number) => { clearTimeout(timer); timer = setTimeout(giveUp, ms); };
    arm(SOCKET_FIRST_FRAME_MS);
    socket.onmessage = (event) => {
      if (settled) return;
      const status = JSON.parse(event.data) as JobStatus;
      onProgress?.(status);
      if (status.status !== "queued" && status.status !== "running") {
        settled = true;
        clearTimeout(timer);
        resolve(status);
        socket.close();
      } else {
        arm(SOCKET_IDLE_MS);
      }
    };
    socket.onerror = giveUp;
    socket.onclose = giveUp;
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
    body.append("contour_map", file);
    return net(`${BASE}/analyzeContour`, { method: "POST", body }).then(json<JobAccepted>);
  },
  /** Phase 3: analyse a box drawn on the map (elevation from Copernicus GLO-30). */
  analyzeArea(bbox: [number, number, number, number]): Promise<JobAccepted> {
    return net(`${BASE}/analyzeArea`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...idem() },
      body: JSON.stringify({ bbox }),
    }).then(json<JobAccepted>);
  },
  job(id: string): Promise<JobStatus> {
    return net(`${BASE}/jobs/${id}`).then(json<JobStatus>);
  },
  contourResult(jobId: string): Promise<ContourAnalysisResult> {
    return net(`${BASE}/analysis/results/contour/${jobId}`).then(json<ContourAnalysisResult>);
  },
  villages(): Promise<Page<VillageOut>> {
    return net(`${BASE}/villages?limit=50`).then(json<Page<VillageOut>>);
  },
  summary(id: string): Promise<VillageSummary> {
    return net(`${BASE}/villages/${id}/summary`).then(json<VillageSummary>);
  },
  layers(id: string): Promise<{ layers: LayerDescriptor[] }> {
    return net(`${BASE}/terrain/${id}/layers`).then(json<{ layers: LayerDescriptor[] }>);
  },
  contours(id: string, interval: number): Promise<ContourResponse> {
    return net(`${BASE}/terrain/${id}/contours?interval=${interval}`).then(json<ContourResponse>);
  },
  streams(id: string): Promise<StreamNetwork> {
    return net(`${BASE}/terrain/${id}/streams`).then(json<StreamNetwork>);
  },
  async catchment(villageId: string, point: PourPoint, onProgress?: Progress): Promise<CatchmentResult> {
    const accepted = await net(`${BASE}/analysis/catchment`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...idem() },
      body: JSON.stringify({ village_id: villageId, pour_point: point }),
    }).then(json<JobAccepted>);
    const status = await waitForJob(accepted.job_id, 800, 120_000, onProgress);
    if (status.status !== "succeeded") throw new Error(status.error?.title ?? `job ${status.status}`);
    return net(`${BASE}/analysis/results/catchment/${accepted.job_id}`).then(json<CatchmentResult>);
  },
  async pondDesign(villageId: string, point: PourPoint, targetReliability = 0.75, onProgress?: Progress): Promise<PondDesignResult> {
    const accepted = await net(`${BASE}/analysis/pond-design`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...idem() },
      body: JSON.stringify({ village_id: villageId, pour_point: point, target_reliability: targetReliability }),
    }).then(json<JobAccepted>);
    const status = await waitForJob(accepted.job_id, 1000, 300_000, onProgress);
    if (status.status !== "succeeded") throw new Error(status.error?.title ?? `job ${status.status}`);
    const design = await net(`${BASE}/analysis/results/pond-design/${accepted.job_id}`).then(json<PondDesignResult>);
    design.job_id = accepted.job_id;
    return design;
  },
  async login(username: string, password: string): Promise<Session> {
    const t = await net(`${BASE}/auth/token`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) }).then(json<{ access_token: string; role: string }>);
    return { username, role: t.role, token: t.access_token };
  },
  saveRecommendation(designJobId: string, token: string): Promise<RecommendationOut> {
    return net(`${BASE}/recommendations`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ design_job_id: designJobId }) }).then(json<RecommendationOut>);
  },
  changeStatus(id: string, status: string, reason: string, token: string): Promise<RecommendationOut> {
    return net(`${BASE}/recommendations/${id}/status`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ status, reason }) }).then(json<RecommendationOut>);
  },
  audit(id: string): Promise<{ audit: { actor: string; action: string; detail: Record<string, unknown> }[] }> {
    return net(`${BASE}/recommendations/${id}/audit`).then(json<{ audit: { actor: string; action: string; detail: Record<string, unknown> }[] }>);
  },
  createExport(id: string, fmt: string): Promise<{ url: string }> {
    return net(`${BASE}/recommendations/${id}/exports?export_format=${fmt}`, { method: "POST" }).then(json<{ url: string }>);
  },
  async suitability(villageId: string, topN = 8, onProgress?: Progress): Promise<SuitabilityResult> {
    const accepted = await net(`${BASE}/analysis/suitability`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...idem() },
      body: JSON.stringify({ village_id: villageId, top_n: topN }),
    }).then(json<JobAccepted>);
    const status = await waitForJob(accepted.job_id, 1500, 600_000, onProgress);
    if (status.status !== "succeeded") throw new Error(status.error?.title ?? `job ${status.status}`);
    return net(`${BASE}/analysis/results/suitability/${accepted.job_id}`).then(json<SuitabilityResult>);
  },
  availableLand(villageId: string): Promise<AvailableLand | null> {
    return net(`${BASE}/villages/${villageId}/available-land`).then((r) => (r.ok ? r.json() : null));
  },
  rainfallStatistics(lon: number, lat: number, years = 45): Promise<RainfallStatistics> {
    return net(`${BASE}/rainfall/statistics?lon=${lon}&lat=${lat}&years=${years}`).then(json<RainfallStatistics>);
  },
  /** The latest contour-analysis result for a village, if the session knows one. */
  siting(id: string): Promise<{ candidate_sites: ContourAnalysisResult["candidate_sites"]; siting: ContourAnalysisResult["siting"] } | null> {
    return net(`${BASE}/villages/${id}/siting`).then((r) => (r.ok ? r.json() : null));
  },
};
