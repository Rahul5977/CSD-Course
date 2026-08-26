/*
 * pond-planner-ui — the design system behind the Village Pond Planner workspace.
 *
 * Rules the components encode: every number is a <Qty> (value big, unit small,
 * uncertainty beside it); every panel has six states (loading, empty, error, stale,
 * offline, job in progress); one primary action per panel; classes come only from
 * styles.css, which is built from web/design/tokens.css + components.css.
 */
import { useState, type ReactNode, type ButtonHTMLAttributes, type AnchorHTMLAttributes } from "react";
import type { Quantity, ResultWarning, JobState } from "./types";

export type { Quantity, ResultWarning, JobState } from "./types";

/** Format a number for display: 0 decimals ≥ 100, 1 decimal ≥ 10, else 2; Indian digit grouping. */
export function fmt(value: number): string {
  const abs = Math.abs(value);
  const digits = abs >= 100 ? 0 : abs >= 10 ? 1 : 2;
  return value.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

export interface QtyProps {
  /** The quantity to show; `null`/`undefined` renders an em dash placeholder. */
  q?: Quantity | null;
  /** Small uppercase label above the value, e.g. "Catchment". */
  label?: string;
  /** `lg` uses the 32 px value step for the one headline number in a panel. */
  size?: "lg";
  /** Short note after the band, e.g. "chosen by cost". Keep it under ~5 words. */
  note?: string;
}

/**
 * A quantity with its unit and uncertainty: `38.3 ha · ±26 %`. The core rule of the
 * system — never render a bare number. Use one `size="lg"` per panel for the headline.
 */
export function Qty({ q, label, size, note }: QtyProps) {
  if (!q) {
    return (
      <div className="qty">{label && <span className="label">{label}</span>}<span className="value muted">—</span></div>
    );
  }
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

export interface QtyGridProps { children: ReactNode }
/** Responsive grid for several `<Qty>` side by side (auto-fit, 120 px minimum). */
export function QtyGrid({ children }: QtyGridProps) {
  return <div className="qty-grid">{children}</div>;
}

export interface QProps { q?: Quantity | null }
/** Inline quantity for prose and table cells: `38.3 ha (±26 %)`. */
export function Q({ q }: QProps) {
  if (!q) return <span className="muted">—</span>;
  return <strong title={q.method ?? undefined}>{fmt(q.value)} {q.unit}{q.uncertainty_pct != null ? ` (±${fmt(q.uncertainty_pct)} %)` : ""}</strong>;
}

export type Tone = "ok" | "warn" | "error" | "info" | "stale" | "offline" | "fixture";
export interface BadgeProps {
  /** Status colour: ok · warn · error · info · stale (served from cache) · offline · fixture (demo data). */
  tone: Tone;
  children: ReactNode;
}
/** Small status pill with a leading dot. Put at most one in a panel header. */
export function Badge({ tone, children }: BadgeProps) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** primary (one per panel) · secondary · ghost (cancel, inline) · danger (reject). */
  variant?: "primary" | "secondary" | "ghost" | "danger";
  /** `sm` for panel footers and rows; default for page-level actions. */
  size?: "sm" | "md";
}
/** The button. Text only — no icons in this system. */
export function Button({ variant = "primary", size = "md", className = "", ...rest }: ButtonProps) {
  return <button className={`btn btn-${variant}${size === "sm" ? " btn-sm" : ""} ${className}`.trim()} {...rest} />;
}

export interface LinkButtonProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md";
}
/** An anchor styled as a button, for navigation actions ("Open the planner"). */
export function LinkButton({ variant = "primary", size = "md", className = "", ...rest }: LinkButtonProps) {
  return <a className={`btn btn-${variant}${size === "sm" ? " btn-sm" : ""} ${className}`.trim()} {...rest} />;
}

export interface PanelProps {
  /** Panel title, sentence case: "Catchment", "Pond design". */
  title: ReactNode;
  /** Muted text after the title: a method or a range, e.g. "AHP · CR 0.004". */
  meta?: ReactNode;
  /** A `<Badge>` for the panel's state. */
  badge?: ReactNode;
  /** Footer row: the panel's one primary action plus a muted hint. */
  footer?: ReactNode;
  children?: ReactNode;
  /** Start collapsed for secondary panels (Layers, Available land). */
  defaultOpen?: boolean;
  id?: string;
}
/**
 * A collapsible panel: header (title · meta · badge · chevron), body, optional footer.
 * The unit of the workspace rail; every panel designs six states (loading, empty,
 * error, stale, offline, job in progress) using Skeleton, Empty, ErrorBox, Badge and Progress.
 */
export function Panel({ title, meta, badge, footer, children, defaultOpen = true, id }: PanelProps) {
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

export interface ProgressProps {
  /** Live job state; `null` shows the submitting placeholder at 3 %. */
  status: JobState | null;
  /** Label used while `status` is null, e.g. "submitting". */
  label?: string;
}
/** Job progress: the real stage label and percentage from the job row — never animated. */
export function Progress({ status, label }: ProgressProps) {
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

export interface CalloutProps {
  /** info (default) · warn · critical · ok. */
  tone?: "info" | "warn" | "critical" | "ok";
  children: ReactNode;
}
/** Left-bordered note for warnings and provenance ("DEM interpolated from 1 m contours…"). */
export function Callout({ tone, children }: CalloutProps) {
  return <div className={`callout${tone && tone !== "info" ? ` callout-${tone}` : ""}`}>{children}</div>;
}

export interface WarningsProps { items?: ResultWarning[] | null }
/** One `<Callout>` per API warning; severity maps info → info, caution → warn, critical → critical. */
export function Warnings({ items }: WarningsProps) {
  if (!items?.length) return null;
  return (
    <>
      {items.map((w) => (
        <Callout key={w.code + w.message.slice(0, 16)} tone={w.severity === "critical" ? "critical" : w.severity === "caution" ? "warn" : "info"}>{w.message}</Callout>
      ))}
    </>
  );
}

export interface ErrorBoxProps {
  /** The API error title or code, e.g. "outside_extent — the point is outside the uploaded map". */
  message: string;
  /** Shows a "Try again" button when given. */
  onRetry?: () => void;
}
/** The panel error state: a critical callout plus an optional retry. */
export function ErrorBox({ message, onRetry }: ErrorBoxProps) {
  return (
    <>
      <Callout tone="critical"><b>Failed</b> — {message}</Callout>
      {onRetry && <button className="btn btn-sm btn-secondary" style={{ justifySelf: "start" }} onClick={onRetry}>Try again</button>}
    </>
  );
}

export interface EmptyProps {
  /** One sentence saying what to do next. */
  children: ReactNode;
  /** Optional single action, usually a secondary `<Button size="sm">`. */
  action?: ReactNode;
}
/** The panel empty state: dashed box, one line, one optional action. */
export function Empty({ children, action }: EmptyProps) {
  return <div className="empty"><span>{children}</span>{action}</div>;
}

export interface SkeletonProps { lines?: number }
/** The panel loading state: one large shimmer line plus `lines - 1` narrower ones. */
export function Skeleton({ lines = 3 }: SkeletonProps) {
  return (
    <div className="stack" aria-busy="true" aria-label="Loading">
      <span className="skel skel-lg" />
      {Array.from({ length: lines - 1 }, (_, i) => <span key={i} className="skel" style={{ width: `${80 - i * 20}%` }} />)}
    </div>
  );
}

export interface FactsProps { rows: [ReactNode, ReactNode][] }
/** Two-column definition list for secondary facts under a headline `<Qty>`. */
export function Facts({ rows }: FactsProps) {
  return (
    <dl className="facts">
      {rows.map(([k, v], i) => (<div key={i} style={{ display: "contents" }}><dt>{k}</dt><dd>{v}</dd></div>))}
    </dl>
  );
}

export interface SiteRowProps {
  /** 1-based rank shown in the circle. */
  rank: number;
  /** One line of facts: "Upstream 38 ha · slope 1.2 %". */
  summary: ReactNode;
  /** Per-criterion scores in [0, 1], drawn as small bars in order. */
  scores: number[];
  /** Total score shown on the right, e.g. 0.82. */
  score: number;
  onSelect?: () => void;
}
/** A ranked candidate site: rank · facts · criterion bars · score. Keyboard-selectable. */
export function SiteRow({ rank, summary, scores, score, onSelect }: SiteRowProps) {
  return (
    <div className="site" role="button" tabIndex={0} onClick={onSelect} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onSelect?.(); }}>
      <span className="rank">{rank}</span>
      <div>
        <div className="small">{summary}</div>
        <div className="bars" style={{ gridTemplateColumns: `repeat(${scores.length}, 1fr)` }}>
          {scores.map((s, i) => <i key={i}><b style={{ width: `${Math.max(0, Math.min(1, s)) * 100}%` }} /></i>)}
        </div>
      </div>
      <span className="score">{score.toFixed(2)}</span>
    </div>
  );
}

export interface LayerRowProps {
  name: string;
  /** Swatch colour (CSS colour string). */
  color: string;
  checked: boolean;
  onChange: () => void;
  /** Muted source text on the right, e.g. "raster". */
  hint?: string;
}
/** A map-layer toggle: checkbox · swatch · name · hint. */
export function LayerRow({ name, color, checked, onChange, hint }: LayerRowProps) {
  return (
    <label className="layer">
      <input type="checkbox" checked={checked} onChange={onChange} />
      <span className="sw" style={{ background: color }} />
      <span className="name">{name}</span>
      {hint && <span className="muted">{hint}</span>}
    </label>
  );
}

export interface DataTableProps {
  /** Column headers; `num: true` right-aligns the column. */
  columns: { label: string; num?: boolean }[];
  /** Row cells in column order. */
  rows: ReactNode[][];
}
/** Dense, striped data table for method comparisons and parcel lists. */
export function DataTable({ columns, rows }: DataTableProps) {
  return (
    <table className="table">
      <thead><tr>{columns.map((c) => <th key={c.label} className={c.num ? "num" : undefined}>{c.label}</th>)}</tr></thead>
      <tbody>
        {rows.map((r, i) => <tr key={i}>{r.map((cell, j) => <td key={j} className={columns[j]?.num ? "num" : undefined}>{cell}</td>)}</tr>)}
      </tbody>
    </table>
  );
}

export interface MarkProps { light?: boolean }
/** The brand mark: contour rings around a pond. `light` for the dark top bar. */
export function Mark({ light }: MarkProps) {
  const a = light ? "#7cc4dc" : "#0b6e8f", b = light ? "#d9b48a" : "#8a5a2b";
  return (
    <svg className="mark" viewBox="0 0 26 26" aria-hidden="true">
      <circle cx="13" cy="13" r="11" fill="none" stroke={a} strokeWidth="1.6" />
      <ellipse cx="13" cy="14" rx="7.5" ry="5.5" fill="none" stroke={b} strokeWidth="1.6" />
      <ellipse cx="13" cy="15" rx="3.5" ry="2.4" fill={a} />
    </svg>
  );
}

export interface TopBarProps {
  /** Brand text after the mark. */
  brand: ReactNode;
  /** Village selector or other controls right after the brand. */
  children?: ReactNode;
  /** Right-aligned controls (language, sign-in). */
  actions?: ReactNode;
}
/** The dark workspace top bar: brand · controls · spacer · actions. */
export function TopBar({ brand, children, actions }: TopBarProps) {
  return (
    <header className="topbar">
      <a className="brand" href="/"><Mark light /><span className="brand-text">{brand}</span></a>
      {children}
      <span className="spacer" />
      {actions}
    </header>
  );
}
