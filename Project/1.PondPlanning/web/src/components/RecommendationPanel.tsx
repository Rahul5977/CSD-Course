import { useState } from "react";
import { api } from "../api";
import type { QuantityOut } from "../types";
import { Badge, Callout, Empty, Panel } from "../ui";

export interface RecommendationOut {
  id: string;
  village_name: string;
  status: "draft" | "submitted" | "approved" | "rejected";
  gross_storage: QuantityOut;
  depth: QuantityOut;
  indicative_cost: QuantityOut;
  confidence: string;
  created_by: string;
}
export interface Session { username: string; role: string; token: string }

/** Save the design, move it through draft → submitted → approved, export it. Role-gated. */
export function RecommendationPanel({ designJobId, session, onLogin, onLogout }: {
  designJobId: string | null;
  session: Session | null;
  onLogin: (s: Session) => void;
  onLogout: () => void;
}) {
  const [rec, setRec] = useState<RecommendationOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [audit, setAudit] = useState<{ actor: string; action: string; detail: Record<string, unknown> }[]>([]);
  const [exportUrl, setExportUrl] = useState<string | null>(null);
  const [user, setUser] = useState("planner");
  const [password, setPassword] = useState("");

  const run = async (fn: () => Promise<void>) => {
    setError(null);
    try { await fn(); } catch (e) { setError((e as Error).message); }
  };
  const login = () => run(async () => onLogin(await api.login(user, password)));
  const save = () => run(async () => { if (designJobId && session) setRec(await api.saveRecommendation(designJobId, session.token)); });
  const move = (status: RecommendationOut["status"], reason: string) => run(async () => {
    if (rec && session) { setRec(await api.changeStatus(rec.id, status, reason, session.token)); setAudit((await api.audit(rec.id)).audit); }
  });
  const exportAs = (fmt: "pdf" | "geojson" | "csv") => run(async () => { if (rec) setExportUrl((await api.createExport(rec.id, fmt)).url); });

  const tone = rec?.status === "approved" ? "ok" : rec?.status === "rejected" ? "error" : rec?.status === "submitted" ? "info" : "warn";
  return (
    <Panel title="Recommendation" badge={rec ? <Badge tone={tone}>{rec.status}</Badge> : undefined} meta={session ? `${session.username} · ${session.role}` : undefined}>
      {!session ? (
        <div className="row">
          <select value={user} onChange={(e) => setUser(e.target.value)} className="inline" aria-label="User">
            <option value="viewer">viewer</option><option value="planner">planner</option><option value="officer">officer</option>
          </select>
          <input type="password" placeholder="password (e.g. planner-demo)" value={password} onChange={(e) => setPassword(e.target.value)} aria-label="Password" />
          <button className="btn btn-sm btn-secondary" onClick={login}>Sign in</button>
        </div>
      ) : (
        <p className="muted">Signed in as <b>{session.username}</b> ({session.role}) · <button className="btn btn-sm btn-ghost" onClick={onLogout}>sign out</button></p>
      )}
      {error && <Callout tone="critical"><b>Not allowed</b> — {error}</Callout>}
      {!designJobId && <Empty>Design a pond first; then save it as a recommendation.</Empty>}
      {!rec && designJobId && <div className="row"><button className="btn btn-sm btn-primary" onClick={save} disabled={!session}>Save this design as a recommendation</button>{!session && <span className="muted">planner or officer</span>}</div>}
      {rec && (
        <>
          <p className="small">{rec.village_name} · {rec.gross_storage.display} · {rec.indicative_cost.display} · created by {rec.created_by}</p>
          <div className="row">
            {rec.status === "draft" && <button className="btn btn-sm btn-primary" onClick={() => move("submitted", "ready for review")}>Submit</button>}
            {rec.status === "submitted" && <button className="btn btn-sm btn-primary" onClick={() => move("approved", "sanctioned")}>Approve (officer)</button>}
            {rec.status === "submitted" && <button className="btn btn-sm btn-danger" onClick={() => move("rejected", "needs a survey")}>Reject</button>}
            {rec.status === "rejected" && <button className="btn btn-sm btn-secondary" onClick={() => move("draft", "rework")}>Back to draft</button>}
            <button className="btn btn-sm btn-secondary" onClick={() => exportAs("pdf")}>PDF</button>
            <button className="btn btn-sm btn-secondary" onClick={() => exportAs("geojson")}>GeoJSON</button>
            <button className="btn btn-sm btn-secondary" onClick={() => exportAs("csv")}>CSV</button>
          </div>
          {exportUrl && <p className="small"><a href={exportUrl} target="_blank" rel="noreferrer">Download the export</a></p>}
          {audit.length > 0 && (
            <details open>
              <summary className="muted">Audit trail ({audit.length})</summary>
              <ul className="muted small">{audit.map((a, i) => <li key={i}>{a.actor}: {a.action} {a.detail ? JSON.stringify(a.detail) : ""}</li>)}</ul>
            </details>
          )}
        </>
      )}
    </Panel>
  );
}
