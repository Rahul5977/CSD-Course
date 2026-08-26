/* Shared UI primitives on the design tokens (web/design → tokens.css, ui.css).
   Every number goes through <Qty>: value big, unit small, uncertainty beside it. */
import { useState, type ReactNode } from "react";
import type { JobStatus, QuantityOut, ResultWarning } from "./types";

export function fmt(value: number): string {
  const abs = Math.abs(value);
  const digits = abs >= 100 ? 0 : abs >= 10 ? 1 : 2;
  return value.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

/** A QuantityOut rendered as value · unit · ±band. `size` picks the type step. */
export function Qty({ q, label, size, note }: { q: QuantityOut | undefined | null; label?: string; size?: "lg"; note?: string }) {
  if (!q) return (
    <div className="qty">{label && <span className="label">{label}</span>}<span className="value muted">—</span></div>
  );
  const band = q.uncertainty_pct != null ? `±${fmt(q.uncertainty_pct)} %` : null;
  const extra = note ?? "";
  const tip = [q.display, q.method].filter(Boolean).join(" — ");
  return (
    <div className={`qty${size === "lg" ? " qty-lg" : ""}`} title={tip || undefined}>
      {label && <span className="label">{label}</span>}
      <span className="value">{fmt(q.value)}<small>{q.unit}</small></span>
      {(band || extra) && <span className="band">{band && <b>{band}</b>}{band && extra ? " · " : ""}{extra}</span>}
    </div>
  );
}

/** Inline quantity for prose and tables: "38.3 ha (±26 %)". */
export function Q({ q }: { q: QuantityOut | undefined | null }) {
  if (!q) return <span className="muted">—</span>;
  return <strong title={q.method ?? undefined}>{fmt(q.value)} {q.unit}{q.uncertainty_pct != null ? ` (±${fmt(q.uncertainty_pct)} %)` : ""}</strong>;
}

export type Tone = "ok" | "warn" | "error" | "info" | "stale" | "offline" | "fixture";
export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

/** A collapsible panel: header (title · meta · badge · chevron), body, optional footer. */
export function Panel({ title, meta, badge, footer, children, defaultOpen = true, id }: {
  title: ReactNode; meta?: ReactNode; badge?: ReactNode; footer?: ReactNode; children?: ReactNode; defaultOpen?: boolean; id?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className={`panel${open ? "" : " collapsed"}`} id={id}>
      <header>
        <h2>{title}</h2>
        {meta && <span className="muted">{meta}</span>}
        {badge}
        <button className="chev" aria-expanded={open} aria-label={open ? "Collapse" : "Expand"} onClick={() => setOpen(!open)}>{open ? "▾" : "▸"}</button>
      </header>
      {open && <div className="body">{children}</div>}
      {open && footer && <footer>{footer}</footer>}
    </section>
  );
}

/** Job progress: real stage label and percentage from the job row. */
export function Progress({ status, label }: { status: JobStatus | null; label?: string }) {
  const pct = status?.progress ?? 3;
  const stage = status?.stage ?? label ?? "submitting";
  const cls = status?.status === "succeeded" ? " job-succeeded" : status?.status === "failed" ? " job-failed" : "";
  return (
    <div className={`job${cls}`} aria-live="polite">
      <div className="meta"><span>{stage}</span><span>{Math.round(pct)} %</span></div>
      <div className="bar"><div className="fill" style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

export function Callout({ tone, children }: { tone?: "info" | "warn" | "critical" | "ok"; children: ReactNode }) {
  return <div className={`callout${tone && tone !== "info" ? ` callout-${tone}` : ""}`}>{children}</div>;
}

/** Result warnings from the API, one callout each, severity → tone. */
export function Warnings({ items }: { items: ResultWarning[] | undefined }) {
  if (!items?.length) return null;
  return (
    <>
      {items.map((w) => (
        <Callout key={w.code + w.message.slice(0, 16)} tone={w.severity === "critical" ? "critical" : w.severity === "caution" ? "warn" : "info"}>{w.message}</Callout>
      ))}
    </>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <>
      <Callout tone="critical"><b>Failed</b> — {message}</Callout>
      {onRetry && <button className="btn btn-sm btn-secondary" style={{ justifySelf: "start" }} onClick={onRetry}>Try again</button>}
    </>
  );
}

export function Empty({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return <div className="empty"><span>{children}</span>{action}</div>;
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="stack" aria-busy="true" aria-label="Loading">
      <span className="skel skel-lg" />
      {Array.from({ length: lines - 1 }, (_, i) => <span key={i} className="skel" style={{ width: `${80 - i * 20}%` }} />)}
    </div>
  );
}

export function Facts({ rows }: { rows: [ReactNode, ReactNode][] }) {
  return (
    <dl className="facts">
      {rows.map(([k, v], i) => (<div key={i} style={{ display: "contents" }}><dt>{k}</dt><dd>{v}</dd></div>))}
    </dl>
  );
}

export function Mark({ light }: { light?: boolean }) {
  const a = light ? "#7cc4dc" : "#0b6e8f", b = light ? "#d9b48a" : "#8a5a2b";
  return (
    <svg className="mark" viewBox="0 0 26 26" aria-hidden="true">
      <circle cx="13" cy="13" r="11" fill="none" stroke={a} strokeWidth="1.6" />
      <ellipse cx="13" cy="14" rx="7.5" ry="5.5" fill="none" stroke={b} strokeWidth="1.6" />
      <ellipse cx="13" cy="15" rx="3.5" ry="2.4" fill={a} />
    </svg>
  );
}
