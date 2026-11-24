import type { ReactNode } from "react";
import type { Provenance, Severity } from "../types";

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function formatNumber(value: number | undefined | null): string {
  return new Intl.NumberFormat().format(value ?? 0);
}

export function formatPercent(value: number | undefined | null): string {
  return `${Math.round((value ?? 0) * 100)}%`;
}

export function ErrorBanner({ message, onClose }: { message: string | null; onClose?: () => void }) {
  if (!message) return null;
  return (
    <div className="banner banner--error" role="alert">
      <span>{message}</span>
      {onClose && (
        <button type="button" className="banner__close" onClick={onClose} aria-label="Dismiss error">
          ×
        </button>
      )}
    </div>
  );
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warning" }) {
  return <div className={`banner banner--${tone}`}>{children}</div>;
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="loading">
      <span className="spinner" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      {detail && <span>{detail}</span>}
    </div>
  );
}

export function SectionHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="section-header">
      <div>
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function StatCard({ label, value, hint, tone }: { label: string; value: string | number; hint?: string; tone?: string }) {
  return (
    <div className={`stat-card ${tone ? `stat-card--${tone}` : ""}`}>
      <span className="stat-card__label">{label}</span>
      <strong className="stat-card__value">{value}</strong>
      {hint && <span className="stat-card__hint">{hint}</span>}
    </div>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

export function ProvenanceBadge({ provenance }: { provenance: Provenance }) {
  return <Badge tone={provenance === "observed" ? "success" : "inferred"}>{provenance}</Badge>;
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge tone={severity}>{severity}</Badge>;
}

export function Modal({ title, children, onClose, width = "640px" }: { title: string; children: ReactNode; onClose: () => void; width?: string }) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        style={{ maxWidth: width }}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal__header">
          <h3>{title}</h3>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close dialog">
            ×
          </button>
        </div>
        <div className="modal__body">{children}</div>
      </div>
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span className="field__label">{label}</span>
      {children}
      {hint && <span className="field__hint">{hint}</span>}
    </label>
  );
}
